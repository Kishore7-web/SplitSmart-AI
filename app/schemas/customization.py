from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------
# CATEGORY SCHEMAS
# --------------------------------------------------

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    icon: str | None = Field(default=None, max_length=30)
    color: str | None = Field(default=None, max_length=30)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    icon: str | None = None
    color: str | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    icon: str | None = None
    color: str | None = None
    is_default: bool = False
    created_at: datetime
    expense_count: int = 0
    total_spent_paise: int = 0


# --------------------------------------------------
# CUSTOM FIELD SCHEMAS
# --------------------------------------------------

class CustomFieldCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    field_type: str = Field(default="text", pattern="^(text|number|date|select)$")
    options: list[str] | None = None
    entity_type: str = Field(default="group", pattern="^(group|activity|expense)$")
    is_required: bool = False


class CustomFieldValueSave(BaseModel):
    field_id: int
    entity_id: int
    value_text: str | None = None


class CustomFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    field_type: str
    options: list[str] | None = None
    entity_type: str
    is_required: bool
    created_at: datetime


# --------------------------------------------------
# CUSTOM ROLE & PERMISSION SCHEMAS
# --------------------------------------------------

AVAILABLE_PERMISSIONS = [
    "manage_group",
    "manage_activities",
    "manage_members",
    "manage_roles",
    "create_expenses",
    "edit_expenses",
    "delete_expenses",
    "manage_evidence",
    "manage_budgets",
    "manage_settlements",
]


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    description: str | None = None
    is_default: bool = False
    permissions: list[str] = Field(default_factory=list)
    member_count: int = 0
    created_at: datetime
