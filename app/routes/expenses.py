from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, ExpenseShare, ExpenseEvidence
from app.schemas.expenses import ExpenseCreate, ExpenseResponse, ExpenseShareResponse
from app.services.expense_calculator import (
    calculate_equal_split,
    calculate_custom_split,
    calculate_percentage_split,
)

router = APIRouter(prefix="/api/groups/{group_id}/expenses", tags=["Expenses"])


def enrich_expense_response(exp: Expense, db: Session) -> ExpenseResponse:
    ev_count = db.query(ExpenseEvidence).filter(ExpenseEvidence.expense_id == exp.id).count()
    return ExpenseResponse(
        id=exp.id,
        group_id=exp.group_id,
        paid_by_member_id=exp.paid_by_member_id,
        description=exp.description,
        total_amount_paise=exp.total_amount_paise,
        split_type=exp.split_type,
        category=exp.category or "General",
        merchant=exp.merchant,
        expense_date=exp.expense_date or exp.created_at,
        created_at=exp.created_at,
        shares=[
            ExpenseShareResponse(id=s.id, member_id=s.member_id, amount_paise=s.amount_paise)
            for s in exp.shares
        ],
        evidence_count=ev_count,
    )


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(group_id: int, data: ExpenseCreate, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

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
        description=data.description.strip(),
        total_amount_paise=data.total_amount_paise,
        split_type=data.split_type,
        category=data.category or "General",
        merchant=data.merchant.strip() if data.merchant else None,
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
            db.commit()

    return enrich_expense_response(expense, db)


@router.get("/", response_model=list[ExpenseResponse])
def get_expenses(
    group_id: int,
    category: str | None = Query(default=None),
    payer_id: int | None = Query(default=None),
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
    if payer_id:
        query = query.filter(Expense.paid_by_member_id == payer_id)

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


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(group_id: int, expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.group_id == group_id, Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(404, "Expense not found")

    # Unlink any attached evidence before deleting
    evidences = db.query(ExpenseEvidence).filter(ExpenseEvidence.expense_id == expense_id).all()
    for ev in evidences:
        ev.expense_id = None
        ev.link_status = "unmatched"

    db.delete(expense)
    db.commit()
