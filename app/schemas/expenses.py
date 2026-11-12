from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ExpenseShareCreate(BaseModel):
    member_id: int
    amount_paise: int = Field(gt=0)


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    total_amount_paise: int = Field(gt=0)
    paid_by_member_id: int
    split_type: str = Field(default="equal", pattern="^(equal|custom|percentage)$")
    participant_ids: list[int] = Field(min_length=1)
    custom_shares: list[ExpenseShareCreate] | None = None
    percentage_shares: dict[int, float] | None = None
    category: str = Field(default="General", max_length=50)
    activity_id: int | None = None
    merchant: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=500)
    status: str = Field(default="confirmed", pattern="^(draft|confirmed)$")
    expense_date: datetime | None = None
    evidence_id: int | None = None


class ExpenseUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=300)
    total_amount_paise: int | None = Field(default=None, gt=0)
    paid_by_member_id: int | None = None
    split_type: str | None = Field(default=None, pattern="^(equal|custom|percentage)$")
    participant_ids: list[int] | None = None
    custom_shares: list[ExpenseShareCreate] | None = None
    percentage_shares: dict[int, float] | None = None
    category: str | None = None
    activity_id: int | None = None
    merchant: str | None = None
    notes: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|confirmed)$")
    expense_date: datetime | None = None


class ExpenseShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    member_id: int
    amount_paise: int


class ExpenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    paid_by_member_id: int
    activity_id: int | None = None
    description: str
    total_amount_paise: int
    split_type: str
    category: str = "General"
    merchant: str | None = None
    notes: str | None = None
    status: str = "confirmed"
    expense_date: datetime | None = None
    created_at: datetime
    shares: list[ExpenseShareResponse] = []
    evidence_count: int = 0
