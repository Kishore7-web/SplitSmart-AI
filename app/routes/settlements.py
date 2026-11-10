from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, Settlement
from app.schemas.settlements import SettlementCreate, SettlementResponse
from app.services.settlement_engine import calculate_member_balances, simplify_debts


router = APIRouter(
    prefix="/api/groups/{group_id}/settlements",
    tags=["Settlements"]
)


def get_group_balances(db: Session, group_id: int):
    expenses = (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(Expense.group_id == group_id)
        .all()
    )

    settlements = (
        db.query(Settlement)
        .filter(
            Settlement.group_id == group_id,
            Settlement.status == "completed"
        )
        .all()
    )

    return calculate_member_balances(expenses, settlements)


@router.get("/balances")
def get_balances(
    group_id: int,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    balances = get_group_balances(db, group_id)

    return {
        "group_id": group_id,
        "balances": [
            {
                "member_id": member_id,
                "balance_paise": balance
            }
            for member_id, balance in balances.items()
        ]
    }


@router.get("/simplified")
def get_simplified_settlements(
    group_id: int,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    balances = get_group_balances(db, group_id)

    return {
        "group_id": group_id,
        "settlements": simplify_debts(balances)
    }


@router.post(
    "/",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED
)
def create_settlement(
    group_id: int,
    data: SettlementCreate,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    if data.from_member_id == data.to_member_id:
        raise HTTPException(400, "Members cannot settle with themselves")

    member_ids = {data.from_member_id, data.to_member_id}

    members = (
        db.query(Member)
        .filter(
            Member.group_id == group_id,
            Member.id.in_(member_ids),
            Member.is_active.is_(True)
        )
        .all()
    )

    if {member.id for member in members} != member_ids:
        raise HTTPException(
            400,
            "Both members must be active members of this group"
        )

    settlement = Settlement(
        group_id=group_id,
        from_member_id=data.from_member_id,
        to_member_id=data.to_member_id,
        amount_paise=data.amount_paise,
        status="pending",
        payment_provider=data.payment_provider or "manual",
        provider_reference=data.provider_reference
    )

    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    return settlement


@router.patch(
    "/{settlement_id}/complete",
    response_model=SettlementResponse
)
def complete_settlement(
    group_id: int,
    settlement_id: int,
    db: Session = Depends(get_db)
):
    settlement = (
        db.query(Settlement)
        .filter(
            Settlement.id == settlement_id,
            Settlement.group_id == group_id
        )
        .first()
    )

    if not settlement:
        raise HTTPException(404, "Settlement not found")

    if settlement.status == "completed":
        return settlement  # Already completed

    settlement.status = "completed"
    settlement.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(settlement)

    return settlement


@router.get(
    "/",
    response_model=list[SettlementResponse]
)
def get_settlement_history(
    group_id: int,
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    query = db.query(Settlement).filter(Settlement.group_id == group_id)
    if status_filter:
        query = query.filter(Settlement.status == status_filter)

    return query.order_by(Settlement.id.desc()).all()
