from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense
from app.schemas.groups import GroupCreate, GroupUpdate, GroupResponse
from app.schemas.members import MemberCreate, MemberUpdate, MemberResponse


router = APIRouter(
    prefix="/api/groups",
    tags=["Groups"]
)


def enrich_group_response(group: Group, db: Session) -> GroupResponse:
    member_count = db.query(Member).filter(Member.group_id == group.id, Member.is_active.is_(True)).count()
    expenses = db.query(Expense).filter(Expense.group_id == group.id).all()
    total_spent = sum(e.total_amount_paise for e in expenses)

    budget = group.budget_paise or 0
    consumed_pct = (total_spent / budget * 100) if budget > 0 else 0.0

    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        activity_type=group.activity_type or "general",
        start_date=group.start_date,
        end_date=group.end_date,
        budget_paise=budget,
        currency=group.currency or "INR",
        created_at=group.created_at,
        member_count=member_count,
        total_expense_paise=total_spent,
        budget_consumed_percentage=round(consumed_pct, 1),
    )


@router.post(
    "/",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED
)
def create_group(
    group_data: GroupCreate,
    db: Session = Depends(get_db)
):
    new_group = Group(
        name=group_data.name.strip(),
        description=group_data.description.strip() if group_data.description else None,
        activity_type=group_data.activity_type or "general",
        start_date=group_data.start_date,
        end_date=group_data.end_date,
        budget_paise=group_data.budget_paise,
        currency=group_data.currency or "INR"
    )

    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    return enrich_group_response(new_group, db)


@router.get("/", response_model=list[GroupResponse])
def get_all_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).order_by(Group.id.desc()).all()
    return [enrich_group_response(g, db) for g in groups]


@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    return enrich_group_response(group, db)


@router.patch("/{group_id}", response_model=GroupResponse)
def update_group(group_id: int, data: GroupUpdate, db: Session = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    if data.name is not None:
        group.name = data.name.strip()
    if data.description is not None:
        group.description = data.description.strip() if data.description else None
    if data.activity_type is not None:
        group.activity_type = data.activity_type
    if data.start_date is not None:
        group.start_date = data.start_date
    if data.end_date is not None:
        group.end_date = data.end_date
    if data.budget_paise is not None:
        group.budget_paise = data.budget_paise
    if data.currency is not None:
        group.currency = data.currency

    db.commit()
    db.refresh(group)
    return enrich_group_response(group, db)


@router.post(
    "/{group_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED
)
def add_member(
    group_id: int,
    member_data: MemberCreate,
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # First member automatically becomes owner if role is default
    existing_count = db.query(Member).filter(Member.group_id == group_id).count()
    assigned_role = member_data.role
    if existing_count == 0 and assigned_role == "member":
        assigned_role = "owner"

    member = Member(
        group_id=group_id,
        name=member_data.name.strip(),
        email=member_data.email.strip() if member_data.email else None,
        phone=member_data.phone.strip() if member_data.phone else None,
        role=assigned_role,
        is_active=True
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    return member


@router.get(
    "/{group_id}/members",
    response_model=list[MemberResponse]
)
def get_group_members(
    group_id: int,
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    return (
        db.query(Member)
        .filter(Member.group_id == group_id)
        .order_by(Member.id)
        .all()
    )


@router.patch(
    "/{group_id}/members/{member_id}",
    response_model=MemberResponse
)
def update_member(
    group_id: int,
    member_id: int,
    data: MemberUpdate,
    db: Session = Depends(get_db)
):
    member = db.query(Member).filter(Member.id == member_id, Member.group_id == group_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if data.name is not None:
        member.name = data.name.strip()
    if data.email is not None:
        member.email = data.email.strip() if data.email else None
    if data.phone is not None:
        member.phone = data.phone.strip() if data.phone else None
    if data.role is not None:
        member.role = data.role
    if data.is_active is not None:
        member.is_active = data.is_active

    db.commit()
    db.refresh(member)
    return member
