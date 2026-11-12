from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import Group, Member, Expense, Settlement, ExpenseEvidence, PaymentTransaction, Activity, CustomCategory, CustomField, CustomRole
from app.schemas.groups import GroupCreate, GroupUpdate, GroupResponse
from app.schemas.members import MemberCreate, MemberUpdate, MemberResponse
from app.core.auth import get_optional_current_user, check_group_permission, ensure_owner_retention, User


router = APIRouter(
    prefix="/api/groups",
    tags=["Groups & Members"]
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
        is_archived=bool(group.is_archived),
        archived_at=group.archived_at,
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
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    user_obj = user if isinstance(user, User) else None
    new_group = Group(
        name=group_data.name.strip(),
        description=group_data.description.strip() if group_data.description else None,
        activity_type=group_data.activity_type or "general",
        start_date=group_data.start_date,
        end_date=group_data.end_date,
        budget_paise=group_data.budget_paise,
        currency=group_data.currency or "INR",
        created_by_user_id=user_obj.id if user_obj else None,
        is_archived=False
    )

    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    # Seed default categories for convenient out-of-the-box experience
    default_cats = ["Food & Dining", "Transportation", "Accommodation", "Tickets & Events", "Shopping", "General"]
    for cat_name in default_cats:
        db.add(CustomCategory(group_id=new_group.id, name=cat_name, is_default=True))
    db.commit()

    # If created by an authenticated user, automatically add them as the group owner
    if user_obj:
        owner_member = Member(
            group_id=new_group.id,
            user_id=user_obj.id,
            name=user_obj.full_name or user_obj.username,
            email=user_obj.email,
            role="owner",
            is_active=True
        )
        db.add(owner_member)
        db.commit()

    return enrich_group_response(new_group, db)


@router.get("/", response_model=list[GroupResponse])
def get_all_groups(
    include_archived: bool = Query(default=False),
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Group)
    if not include_archived:
        query = query.filter(Group.is_archived.is_(False))

    groups = query.order_by(Group.id.desc()).all()
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
def update_group(
    group_id: int,
    data: GroupUpdate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    check_group_permission(db, group_id, user, "manage_group")

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
    if data.is_archived is not None:
        group.is_archived = data.is_archived
        if data.is_archived and not group.archived_at:
            group.archived_at = datetime.now(timezone.utc)
        elif not data.is_archived:
            group.archived_at = None

    db.commit()
    db.refresh(group)
    return enrich_group_response(group, db)


@router.post("/{group_id}/archive", response_model=GroupResponse)
def archive_group(
    group_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_group")

    group.is_archived = True
    group.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(group)
    return enrich_group_response(group, db)


@router.post("/{group_id}/restore", response_model=GroupResponse)
def restore_group(
    group_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_group")

    group.is_archived = False
    group.archived_at = None
    db.commit()
    db.refresh(group)
    return enrich_group_response(group, db)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Safely delete group and cleanly clean up all dependencies.
    Checked against permissions and ensures no orphaned records.
    """
    group = db.get(Group, group_id)
    if not group:
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_group")

    db.delete(group)
    db.commit()


# =============================================================================
# MEMBER MANAGEMENT
# =============================================================================

@router.post(
    "/{group_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED
)
def add_member(
    group_id: int,
    member_data: MemberCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    check_group_permission(db, group_id, user, "manage_members")

    existing_count = db.query(Member).filter(Member.group_id == group_id).count()
    assigned_role = member_data.role
    if existing_count == 0 and assigned_role == "member":
        assigned_role = "owner"

    member = Member(
        group_id=group_id,
        user_id=member_data.user_id,
        custom_role_id=member_data.custom_role_id,
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
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    member = db.query(Member).filter(Member.id == member_id, Member.group_id == group_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    check_group_permission(db, group_id, user, "manage_members")

    if data.role is not None:
        ensure_owner_retention(db, group_id, member_id, new_role=data.role)
        member.role = data.role

    if data.name is not None:
        member.name = data.name.strip()
    if data.email is not None:
        member.email = data.email.strip() if data.email else None
    if data.phone is not None:
        member.phone = data.phone.strip() if data.phone else None
    if data.custom_role_id is not None:
        member.custom_role_id = data.custom_role_id if data.custom_role_id > 0 else None
    if data.user_id is not None:
        member.user_id = data.user_id if data.user_id > 0 else None
    if data.is_active is not None:
        if not data.is_active:
            ensure_owner_retention(db, group_id, member_id, is_deleting=True)
        member.is_active = data.is_active

    db.commit()
    db.refresh(member)
    return member


@router.delete(
    "/{group_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    group_id: int,
    member_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    member = db.query(Member).filter(Member.id == member_id, Member.group_id == group_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    check_group_permission(db, group_id, user, "manage_members")
    ensure_owner_retention(db, group_id, member_id, is_deleting=True)

    # Check if member has recorded expenses or shares
    has_expenses = db.query(Expense).filter(Expense.paid_by_member_id == member_id).count() > 0
    if has_expenses:
        # Soft delete / deactivate to preserve historical ledger integrity
        member.is_active = False
        db.commit()
    else:
        db.delete(member)
        db.commit()
