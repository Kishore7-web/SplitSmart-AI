import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.database.database import get_db
from app.database.models import (
    Group,
    Expense,
    Member,
    CustomCategory,
    CustomField,
    CustomFieldValue,
    CustomRole,
    RolePermission,
)
from app.schemas.customization import (
    CategoryCreate,
    CategoryUpdate,
    CategoryResponse,
    CustomFieldCreate,
    CustomFieldValueSave,
    CustomFieldResponse,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    AVAILABLE_PERMISSIONS,
)
from app.core.auth import get_optional_current_user, check_group_permission, User


router = APIRouter(
    prefix="/api/groups/{group_id}/customization",
    tags=["Customization: Categories, Fields & Roles"]
)


# =============================================================================
# 1. CUSTOM CATEGORIES
# =============================================================================

@router.get("/categories", response_model=list[CategoryResponse])
def list_categories(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    cats = db.query(CustomCategory).filter(CustomCategory.group_id == group_id).all()
    res = []
    for c in cats:
        exp_count = db.query(Expense).filter(Expense.group_id == group_id, Expense.category == c.name).count()
        spent = sum(e.total_amount_paise for e in db.query(Expense).filter(Expense.group_id == group_id, Expense.category == c.name).all())
        res.append(CategoryResponse(
            id=c.id,
            group_id=c.group_id,
            name=c.name,
            icon=c.icon,
            color=c.color,
            is_default=c.is_default,
            created_at=c.created_at,
            expense_count=exp_count,
            total_spent_paise=spent
        ))
    return res


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    group_id: int,
    data: CategoryCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_group")

    existing = db.query(CustomCategory).filter(
        CustomCategory.group_id == group_id,
        CustomCategory.name.ilike(data.name.strip())
    ).first()
    if existing:
        raise HTTPException(400, f"Category '{data.name}' already exists in this group.")

    cat = CustomCategory(
        group_id=group_id,
        name=data.name.strip(),
        icon=data.icon,
        color=data.color,
        is_default=False
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    return CategoryResponse(
        id=cat.id,
        group_id=cat.group_id,
        name=cat.name,
        icon=cat.icon,
        color=cat.color,
        is_default=cat.is_default,
        created_at=cat.created_at,
        expense_count=0,
        total_spent_paise=0
    )


@router.patch("/categories/{cat_id}", response_model=CategoryResponse)
def update_category(
    group_id: int,
    cat_id: int,
    data: CategoryUpdate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    cat = db.query(CustomCategory).filter(
        CustomCategory.id == cat_id,
        CustomCategory.group_id == group_id
    ).first()
    if not cat:
        raise HTTPException(404, "Category not found")

    check_group_permission(db, group_id, user, "manage_group")

    old_name = cat.name
    if data.name is not None and data.name.strip():
        new_name = data.name.strip()
        cat.name = new_name
        # Update expenses that were using this category name
        db.query(Expense).filter(
            Expense.group_id == group_id,
            Expense.category == old_name
        ).update({"category": new_name})

    if data.icon is not None:
        cat.icon = data.icon
    if data.color is not None:
        cat.color = data.color

    db.commit()
    db.refresh(cat)

    exp_count = db.query(Expense).filter(Expense.group_id == group_id, Expense.category == cat.name).count()
    spent = sum(e.total_amount_paise for e in db.query(Expense).filter(Expense.group_id == group_id, Expense.category == cat.name).all())

    return CategoryResponse(
        id=cat.id,
        group_id=cat.group_id,
        name=cat.name,
        icon=cat.icon,
        color=cat.color,
        is_default=cat.is_default,
        created_at=cat.created_at,
        expense_count=exp_count,
        total_spent_paise=spent
    )


@router.delete("/categories/{cat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    group_id: int,
    cat_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    cat = db.query(CustomCategory).filter(
        CustomCategory.id == cat_id,
        CustomCategory.group_id == group_id
    ).first()
    if not cat:
        raise HTTPException(404, "Category not found")

    check_group_permission(db, group_id, user, "manage_group")

    # Set expenses under this category to "General"
    db.query(Expense).filter(
        Expense.group_id == group_id,
        Expense.category == cat.name
    ).update({"category": "General"})

    db.delete(cat)
    db.commit()


# =============================================================================
# 2. CUSTOM FIELDS
# =============================================================================

@router.get("/custom-fields", response_model=list[CustomFieldResponse])
def list_custom_fields(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    fields = db.query(CustomField).filter(CustomField.group_id == group_id).all()
    res = []
    for f in fields:
        opts = json.loads(f.options_json) if f.options_json else None
        res.append(CustomFieldResponse(
            id=f.id,
            group_id=f.group_id,
            name=f.name,
            field_type=f.field_type,
            options=opts,
            entity_type=f.entity_type,
            is_required=f.is_required,
            created_at=f.created_at
        ))
    return res


@router.post("/custom-fields", response_model=CustomFieldResponse, status_code=status.HTTP_201_CREATED)
def create_custom_field(
    group_id: int,
    data: CustomFieldCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_group")

    options_str = json.dumps(data.options) if data.options else None

    field = CustomField(
        group_id=group_id,
        name=data.name.strip(),
        field_type=data.field_type,
        options_json=options_str,
        entity_type=data.entity_type,
        is_required=data.is_required
    )
    db.add(field)
    db.commit()
    db.refresh(field)

    return CustomFieldResponse(
        id=field.id,
        group_id=field.group_id,
        name=field.name,
        field_type=field.field_type,
        options=data.options,
        entity_type=field.entity_type,
        is_required=field.is_required,
        created_at=field.created_at
    )


@router.delete("/custom-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_field(
    group_id: int,
    field_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    field = db.query(CustomField).filter(
        CustomField.id == field_id,
        CustomField.group_id == group_id
    ).first()
    if not field:
        raise HTTPException(404, "Custom field not found")

    check_group_permission(db, group_id, user, "manage_group")

    db.delete(field)
    db.commit()


# =============================================================================
# 3. CUSTOM ROLES & PERMISSIONS
# =============================================================================

@router.get("/roles", response_model=list[RoleResponse])
def list_custom_roles(group_id: int, db: Session = Depends(get_db)):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    roles = (
        db.query(CustomRole)
        .options(selectinload(CustomRole.permissions))
        .filter(CustomRole.group_id == group_id)
        .all()
    )

    res = []
    for r in roles:
        m_count = db.query(Member).filter(Member.custom_role_id == r.id).count()
        res.append(RoleResponse(
            id=r.id,
            group_id=r.group_id,
            name=r.name,
            description=r.description,
            is_default=r.is_default,
            permissions=[p.permission_key for p in r.permissions],
            member_count=m_count,
            created_at=r.created_at
        ))
    return res


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_custom_role(
    group_id: int,
    data: RoleCreate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    if not db.get(Group, group_id):
        raise HTTPException(404, "Group not found")

    check_group_permission(db, group_id, user, "manage_roles")

    role = CustomRole(
        group_id=group_id,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        is_default=False
    )
    db.add(role)
    db.flush()

    for perm_key in data.permissions:
        if perm_key in AVAILABLE_PERMISSIONS:
            db.add(RolePermission(role_id=role.id, permission_key=perm_key))

    db.commit()
    db.refresh(role)

    return RoleResponse(
        id=role.id,
        group_id=role.group_id,
        name=role.name,
        description=role.description,
        is_default=role.is_default,
        permissions=[p.permission_key for p in role.permissions],
        member_count=0,
        created_at=role.created_at
    )


@router.patch("/roles/{role_id}", response_model=RoleResponse)
def update_custom_role(
    group_id: int,
    role_id: int,
    data: RoleUpdate,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    role = db.query(CustomRole).filter(
        CustomRole.id == role_id,
        CustomRole.group_id == group_id
    ).first()
    if not role:
        raise HTTPException(404, "Role not found")

    check_group_permission(db, group_id, user, "manage_roles")

    if data.name is not None:
        role.name = data.name.strip()
    if data.description is not None:
        role.description = data.description.strip() if data.description else None

    if data.permissions is not None:
        # Replace permissions
        db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        for perm_key in data.permissions:
            if perm_key in AVAILABLE_PERMISSIONS:
                db.add(RolePermission(role_id=role.id, permission_key=perm_key))

    db.commit()
    db.refresh(role)

    m_count = db.query(Member).filter(Member.custom_role_id == role.id).count()

    return RoleResponse(
        id=role.id,
        group_id=role.group_id,
        name=role.name,
        description=role.description,
        is_default=role.is_default,
        permissions=[p.permission_key for p in role.permissions],
        member_count=m_count,
        created_at=role.created_at
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_role(
    group_id: int,
    role_id: int,
    user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    role = db.query(CustomRole).filter(
        CustomRole.id == role_id,
        CustomRole.group_id == group_id
    ).first()
    if not role:
        raise HTTPException(404, "Role not found")

    check_group_permission(db, group_id, user, "manage_roles")

    # Unlink members with this custom role
    db.query(Member).filter(Member.custom_role_id == role_id).update({"custom_role_id": None})
    db.delete(role)
    db.commit()
