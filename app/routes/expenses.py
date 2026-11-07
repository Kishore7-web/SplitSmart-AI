
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, ExpenseShare
from app.schemas.expenses import ExpenseCreate, ExpenseResponse
from app.services.expense_calculator import (
    calculate_equal_split,
    calculate_custom_split
)

router = APIRouter(prefix="/api/groups/{group_id}/expenses", tags=["Expenses"])


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

    if data.split_type == "equal":
        if data.custom_shares is not None:
            raise HTTPException(400, "Do not provide custom shares for an equal split")
        shares = calculate_equal_split(data.total_amount_paise, participant_ids)
    else:
        if not data.custom_shares:
            raise HTTPException(400, "Custom shares are required")
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
        split_type=data.split_type
    )

    expense.shares = [
        ExpenseShare(member_id=member_id, amount_paise=amount)
        for member_id, amount in shares.items()
    ]

    db.add(expense)
    db.commit()

    return (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(Expense.id == expense.id)
        .one()
    )


@router.get("/", response_model=list[ExpenseResponse])
def get_expenses(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    return (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(Expense.group_id == group_id)
        .order_by(Expense.id.desc())
        .all()
    )

