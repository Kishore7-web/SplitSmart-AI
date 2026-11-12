from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, ExpenseShare, ExpenseEvidence, Activity
from app.schemas.expenses import ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseShareResponse
from app.services.expense_calculator import (
    calculate_equal_split,
    calculate_custom_split,
    calculate_percentage_split,
)
from app.core.auth import get_optional_current_user, check_group_permission, User

router = APIRouter(prefix="/api/groups/{group_id}/expenses", tags=["Expenses"])


def enrich_expense_response(exp: Expense, db: Session) -> ExpenseResponse:
    ev_count = db.query(ExpenseEvidence).filter(ExpenseEvidence.expense_id == exp.id).count()
    return ExpenseResponse(
        id=exp.id,
        group_id=exp.group_id,
        paid_by_member_id=exp.paid_by_member_id,
        activity_id=exp.activity_id,
        description=exp.description,
        total_amount_paise=exp.total_amount_paise,
        split_type=exp.split_type,
        category=exp.category or "General",
        merchant=exp.merchant,
        notes=exp.notes,
        status=exp.status or "confirmed",
        expense_date=exp.expense_date or exp.created_at,
        created_at=exp.created_at,
        shares=[
            ExpenseShareResponse(id=s.id, member_id=s.member_id, amount_paise=s.amount_paise)
            for s in exp.shares
        ],
        evidence_count=ev_count,
    )


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    group_id: int,
    data: ExpenseCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "create_expenses")

    if data.activity_id:
        act = db.query(Activity).filter(Activity.id == data.activity_id, Activity.group_id == group_id).first()
        if not act:
            raise HTTPException(400, "Specified activity does not belong to this group.")

    participant_ids = data.participant_ids

    if len(set(participant_ids)) != len(participant_ids):
        raise HTTPException(400, "Duplicate participants are not allowed")

    required_ids = set(participant_ids) | {data.paid_by_member_id}
    members = db.query(Member).filter(
        Member.group_id == group_id,
        Member.id.in_(required_ids),
        Member.is_active.is_(True)
    ).all()

    if {member.id for member in members} != required_ids:
        raise HTTPException(400, "Payer or participant is not an active member of this group")

    # Split calculations
    if data.split_type == "equal":
        shares = calculate_equal_split(data.total_amount_paise, participant_ids)
    elif data.split_type == "percentage":
        if not data.percentage_shares:
            raise HTTPException(400, "Percentage shares are required for percentage split")
        if set(data.percentage_shares.keys()) != set(participant_ids):
            raise HTTPException(400, "Percentage shares must match participants exactly")
        shares = calculate_percentage_split(data.total_amount_paise, data.percentage_shares)
    else:
        # Custom split
        if not data.custom_shares:
            raise HTTPException(400, "Custom shares are required for custom split")
        custom_ids = [share.member_id for share in data.custom_shares]
        if len(set(custom_ids)) != len(custom_ids) or set(custom_ids) != set(participant_ids):
            raise HTTPException(400, "Custom shares must match the participants exactly")
        shares = calculate_custom_split(
            data.total_amount_paise,
            {share.member_id: share.amount_paise for share in data.custom_shares}
        )

    expense = Expense(
        group_id=group_id,
        paid_by_member_id=data.paid_by_member_id,
        activity_id=data.activity_id,
        description=data.description.strip(),
        total_amount_paise=data.total_amount_paise,
        split_type=data.split_type,
        category=data.category or "General",
        merchant=data.merchant.strip() if data.merchant else None,
        notes=data.notes.strip() if data.notes else None,
        status=data.status or "confirmed",
        expense_date=data.expense_date or datetime.now(timezone.utc),
    )

    expense.shares = [
        ExpenseShare(member_id=member_id, amount_paise=amount)
        for member_id, amount in shares.items()
    ]

    db.add(expense)
    db.commit()
    db.refresh(expense)

    # Link evidence if provided
    if data.evidence_id:
        evidence = db.query(ExpenseEvidence).filter(
            ExpenseEvidence.id == data.evidence_id,
            ExpenseEvidence.group_id == group_id
        ).first()
        if evidence:
            evidence.expense_id = expense.id
            evidence.link_status = "confirmed"
            if data.activity_id:
                evidence.activity_id = data.activity_id
            db.commit()

    return enrich_expense_response(expense, db)


@router.get("/", response_model=list[ExpenseResponse])
def get_expenses(
    group_id: int,
    category: str | None = Query(default=None),
    activity_id: int | None = Query(default=None),
    payer_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    query = (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(Expense.group_id == group_id)
    )

    if category:
        query = query.filter(Expense.category == category)
    if activity_id:
        query = query.filter(Expense.activity_id == activity_id)
    if payer_id:
        query = query.filter(Expense.paid_by_member_id == payer_id)
    if status_filter:
        query = query.filter(Expense.status == status_filter)

    expenses = query.order_by(Expense.id.desc()).all()
    return [enrich_expense_response(exp, db) for exp in expenses]


@router.get("/{expense_id}", response_model=ExpenseResponse)
def get_expense(group_id: int, expense_id: int, db: Session = Depends(get_db)):
    expense = (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(Expense.group_id == group_id, Expense.id == expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(404, "Expense not found")

    return enrich_expense_response(expense, db)


@router.patch("/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    group_id: int,
    expense_id: int,
    data: ExpenseUpdate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    expense = (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(Expense.group_id == group_id, Expense.id == expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(404, "Expense not found")

    check_group_permission(db, group_id, user, "edit_expenses")

    if data.description is not None:
        expense.description = data.description.strip()
    if data.category is not None:
        expense.category = data.category
    if data.activity_id is not None:
        expense.activity_id = data.activity_id if data.activity_id > 0 else None
    if data.merchant is not None:
        expense.merchant = data.merchant.strip() if data.merchant else None
    if data.notes is not None:
        expense.notes = data.notes.strip() if data.notes else None
    if data.status is not None:
        expense.status = data.status
    if data.expense_date is not None:
        expense.expense_date = data.expense_date

    # If amount, payer or participants changed, recalculate shares
    new_amount = data.total_amount_paise or expense.total_amount_paise
    new_payer_id = data.paid_by_member_id or expense.paid_by_member_id
    new_split_type = data.split_type or expense.split_type

    if data.total_amount_paise is not None or data.participant_ids is not None or data.paid_by_member_id is not None or data.split_type is not None:
        participant_ids = data.participant_ids or [s.member_id for s in expense.shares]
        if not participant_ids:
            participant_ids = [new_payer_id]

        if new_split_type == "equal":
            shares = calculate_equal_split(new_amount, participant_ids)
        elif new_split_type == "percentage":
            if not data.percentage_shares:
                raise HTTPException(400, "Percentage shares required")
            shares = calculate_percentage_split(new_amount, data.percentage_shares)
        else:
            if not data.custom_shares:
                raise HTTPException(400, "Custom shares required")
            shares = calculate_custom_split(new_amount, {cs.member_id: cs.amount_paise for cs in data.custom_shares})

        expense.total_amount_paise = new_amount
        expense.paid_by_member_id = new_payer_id
        expense.split_type = new_split_type

        # Replace shares
        db.query(ExpenseShare).filter(ExpenseShare.expense_id == expense.id).delete()
        expense.shares = [
            ExpenseShare(member_id=mid, amount_paise=amt)
            for mid, amt in shares.items()
        ]

    expense.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(expense)

    return enrich_expense_response(expense, db)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    group_id: int,
    expense_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    expense = db.query(Expense).filter(Expense.group_id == group_id, Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(404, "Expense not found")

    check_group_permission(db, group_id, user, "delete_expenses")

    # Unlink any attached evidence before deleting
    evidences = db.query(ExpenseEvidence).filter(ExpenseEvidence.expense_id == expense_id).all()
    for ev in evidences:
        ev.expense_id = None
        ev.link_status = "unmatched"

    db.delete(expense)
    db.commit()
