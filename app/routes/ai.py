
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, ExpenseShare
from app.schemas.ai import AIParseRequest, AIParseResponse
from app.schemas.expenses import ExpenseResponse
from app.services.ai_service import parse_expense_with_ai
from app.services.expense_calculator import calculate_equal_split


router = APIRouter(
    prefix="/api/ai",
    tags=["AI Assistant"]
)


def extract_expense_details(data: AIParseRequest, db: Session):
    group = db.get(Group, data.group_id)

    if not group:
        raise HTTPException(404, "Group not found")

    members = (
        db.query(Member)
        .filter(
            Member.group_id == data.group_id,
            Member.is_active.is_(True)
        )
        .all()
    )

    if not members:
        raise HTTPException(400, "This group has no active members")

    member_lookup = {
        member.name.strip().casefold(): member.id
        for member in members
    }

    try:
        parsed = parse_expense_with_ai(
            data.text,
            [member.name for member in members]
        )

        amount = Decimal(str(parsed["amount_rupees"]))

        if not amount.is_finite() or amount <= 0:
            raise ValueError("Expense amount must be positive.")

        paise = int(
            (amount * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP
            )
        )

        if paise <= 0 or paise > 2_000_000_000:
            raise ValueError("Expense amount is outside the allowed range.")

        payer_name = parsed["payer_name"].strip().casefold()

        if payer_name not in member_lookup:
            raise ValueError("Payer is not a member of this group.")

        participant_ids = []

        for name in parsed["participants"]:
            if not isinstance(name, str):
                raise ValueError("Invalid participant name.")

            key = name.strip().casefold()

            if key not in member_lookup:
                raise ValueError(f"Unknown group member: {name}")

            member_id = member_lookup[key]

            if member_id not in participant_ids:
                participant_ids.append(member_id)

        if not participant_ids:
            raise ValueError("At least one participant is required.")

        description = parsed["description"].strip()

        if not description:
            raise ValueError("Expense description cannot be empty.")

        return {
            "description": description,
            "amount_paise": paise,
            "paid_by_member_id": member_lookup[payer_name],
            "participant_ids": participant_ids,
            "split_type": parsed["split_type"]
        }

    except (ValueError, InvalidOperation, KeyError, TypeError) as exc:
        raise HTTPException(400, str(exc))


@router.post(
    "/parse-expense",
    response_model=AIParseResponse
)
def parse_expense(
    data: AIParseRequest,
    db: Session = Depends(get_db)
):
    details = extract_expense_details(data, db)

    return AIParseResponse(
        description=details["description"],
        amount_paise=details["amount_paise"],
        paid_by_member_id=details["paid_by_member_id"],
        participant_ids=details["participant_ids"],
        split_type=details["split_type"]
    )


@router.post(
    "/create-expense",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED
)
def create_expense_using_ai(
    data: AIParseRequest,
    db: Session = Depends(get_db)
):
    details = extract_expense_details(data, db)

    if details["split_type"] != "equal":
        raise HTTPException(
            400,
            "AI automatic creation currently supports equal splits only. "
            "Use the regular Expenses API for custom splits."
        )

    shares = calculate_equal_split(
        details["amount_paise"],
        details["participant_ids"]
    )

    expense = Expense(
        group_id=data.group_id,
        paid_by_member_id=details["paid_by_member_id"],
        description=details["description"],
        total_amount_paise=details["amount_paise"],
        split_type="equal"
    )

    expense.shares = [
        ExpenseShare(
            member_id=member_id,
            amount_paise=amount
        )
        for member_id, amount in shares.items()
    ]

    try:
        db.add(expense)
        db.commit()
        db.refresh(expense)

        return (
            db.query(Expense)
            .options(selectinload(Expense.shares))
            .filter(Expense.id == expense.id)
            .one()
        )

    except Exception:
        db.rollback()
        raise
