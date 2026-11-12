from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ActivityCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    budget_paise: int = Field(default=0, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None


class ActivityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    budget_paise: int | None = Field(default=None, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = Field(default=None, pattern="^(active|completed|archived)$")


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    description: str | None = None
    budget_paise: int = 0
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str = "active"
    created_at: datetime
    spent_paise: int = 0
    remaining_paise: int = 0
    expense_count: int = 0
