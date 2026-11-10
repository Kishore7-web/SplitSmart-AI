from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    activity_type: str = Field(default="general", max_length=50)
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_paise: int = Field(default=0, ge=0)
    currency: str = Field(default="INR", max_length=10)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    activity_type: str | None = Field(default=None, max_length=50)
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_paise: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    activity_type: str = "general"
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_paise: int = 0
    currency: str = "INR"
    created_at: datetime
    member_count: int | None = 0
    total_expense_paise: int | None = 0
    budget_consumed_percentage: float | None = 0.0
