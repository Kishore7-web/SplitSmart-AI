
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ExpenseShareCreate(BaseModel):
    member_id: int
    amount_paise: int = Field(gt=0)


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    total_amount_paise: int = Field(gt=0)
    paid_by_member_id: int
    split_type: str = Field(pattern="^(equal|custom)$")
    participant_ids: list[int] = Field(min_length=1)
    custom_shares: list[ExpenseShareCreate] | None = None


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
    description: str
    total_amount_paise: int
    split_type: str
    created_at: datetime
    shares: list[ExpenseShareResponse]
