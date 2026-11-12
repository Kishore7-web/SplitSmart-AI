from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, Settlement
from app.schemas.settlements import (
    SettlementCreate,
    SettlementResponse,
    SettlementSuggestion,
    GroupSettlementSummary,
)
from app.services.settlement_engine import calculate_member_balances, simplify_debts
from app.core.auth import get_optional_current_user, check_group_permission, User


router = APIRouter(
    prefix="/api/groups/{group_id}/settlements",
    tags=["Settlements & Balances"]
)


def get_group_balances(db: Session, group_id: int):
    # Only confirmed expenses affect official financial balances
    expenses = (
        db.query(Expense)
        .options(selectinload(Expense.shares))
        .filter(
            Expense.group_id == group_id,
            Expense.status == "confirmed"
        )
        .all()
    )

    # Only completed settlements reduce balances
    settlements = (
        db.query(Settlement)
        .filter(
            Settlement.group_id == group_id,
            Settlement.status == "completed"
        )
        .all()
    )

    return calculate_member_balances(expenses, settlements)


def to_settlement_response(st: Settlement, db: Session) -> SettlementResponse:
    sender = db.get(Member, st.from_member_id)
    receiver = db.get(Member, st.to_member_id)
    return SettlementResponse(
        id=st.id,
        group_id=st.group_id,
        from_member_id=st.from_member_id,
        to_member_id=st.to_member_id,
        from_member_name=sender.name if sender else f"Member #{st.from_member_id}",
        to_member_name=receiver.name if receiver else f"Member #{st.to_member_id}",
        amount_paise=st.amount_paise,
        status=st.status,
        payment_provider=st.payment_provider,
        provider_reference=st.provider_reference,
        notes=st.notes,
        parent_settlement_id=st.parent_settlement_id,
        created_at=st.created_at,
        completed_at=st.completed_at,
    )


@router.get("/balances")
def get_balances(
    group_id: int,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    balances = get_group_balances(db, group_id)
    members = db.query(Member).filter(Member.group_id == group_id).all()
    name_map = {m.id: m.name for m in members}

    return {
        "group_id": group_id,
        "balances": [
            {
                "member_id": member_id,
                "member_name": name_map.get(member_id, f"Member #{member_id}"),
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
    raw_suggestions = simplify_debts(balances)

    members = db.query(Member).filter(Member.group_id == group_id).all()
    name_map = {m.id: m.name for m in members}

    suggestions = []
    for s in raw_suggestions:
        f_id = s["from_member_id"]
        t_id = s["to_member_id"]
        suggestions.append({
            "from_member_id": f_id,
            "from_member_name": name_map.get(f_id, f"Member #{f_id}"),
            "to_member_id": t_id,
            "to_member_name": name_map.get(t_id, f"Member #{t_id}"),
            "amount_paise": s["amount_paise"],
            "from_member_net_balance_paise": balances.get(f_id, 0),
            "to_member_net_balance_paise": balances.get(t_id, 0),
        })

    return {
        "group_id": group_id,
        "settlements": suggestions
    }


@router.get("/summary", response_model=GroupSettlementSummary)
def get_settlement_summary(
    group_id: int,
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    all_settlements = db.query(Settlement).filter(Settlement.group_id == group_id).all()
    completed = [s for s in all_settlements if s.status == "completed"]
    pending = [s for s in all_settlements if s.status == "pending"]

    total_settled = sum(s.amount_paise for s in completed)
    total_pending = sum(s.amount_paise for s in pending)

    balances = get_group_balances(db, group_id)
    raw_suggestions = simplify_debts(balances)

    members = db.query(Member).filter(Member.group_id == group_id).all()
    name_map = {m.id: m.name for m in members}

    suggestions = []
    for s in raw_suggestions:
        f_id = s["from_member_id"]
        t_id = s["to_member_id"]
        suggestions.append(SettlementSuggestion(
            from_member_id=f_id,
            from_member_name=name_map.get(f_id, f"Member #{f_id}"),
            to_member_id=t_id,
            to_member_name=name_map.get(t_id, f"Member #{t_id}"),
            amount_paise=s["amount_paise"],
            from_member_net_balance_paise=balances.get(f_id, 0),
            to_member_net_balance_paise=balances.get(t_id, 0),
        ))

    member_balances_list = [
        {
            "member_id": mid,
            "member_name": name_map.get(mid, f"Member #{mid}"),
            "balance_paise": bal,
            "status": "owes" if bal < 0 else ("receives" if bal > 0 else "settled")
        }
        for mid, bal in balances.items()
    ]

    return GroupSettlementSummary(
        group_id=group_id,
        total_settled_paise=total_settled,
        total_pending_paise=total_pending,
        pending_count=len(pending),
        completed_count=len(completed),
        suggestions=suggestions,
        member_balances=member_balances_list
    )


@router.post(
    "/",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED
)
def create_settlement(
    group_id: int,
    data: SettlementCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_settlements")

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
        provider_reference=data.provider_reference,
        notes=data.notes,
        parent_settlement_id=data.parent_settlement_id
    )

    db.add(settlement)
    db.commit()
    db.refresh(settlement)

    return to_settlement_response(settlement, db)


@router.patch(
    "/{settlement_id}/complete",
    response_model=SettlementResponse
)
def complete_settlement(
    group_id: int,
    settlement_id: int,
    user: User | None = Depends(get_optional_current_user),
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

    check_group_permission(db, group_id, user, "manage_settlements")

    if settlement.status == "completed":
        return to_settlement_response(settlement, db)

    settlement.status = "completed"
    settlement.completed_at = datetime.now(timezone.utc)
    settlement.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(settlement)

    return to_settlement_response(settlement, db)


@router.patch(
    "/{settlement_id}/cancel",
    response_model=SettlementResponse
)
def cancel_settlement(
    group_id: int,
    settlement_id: int,
    user: User | None = Depends(get_optional_current_user),
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

    check_group_permission(db, group_id, user, "manage_settlements")

    settlement.status = "cancelled"
    settlement.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(settlement)

    return to_settlement_response(settlement, db)


@router.delete(
    "/{settlement_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_settlement(
    group_id: int,
    settlement_id: int,
    user: User | None = Depends(get_optional_current_user),
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

    check_group_permission(db, group_id, user, "manage_settlements")

    db.delete(settlement)
    db.commit()
    return None


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

    settlements = query.order_by(Settlement.id.desc()).all()
    return [to_settlement_response(s, db) for s in settlements]
