
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SettlementCreate(BaseModel):
    from_member_id: int
    to_member_id: int
    amount_paise: int = Field(gt=0)
    payment_provider: str | None = Field(default=None, max_length=50)


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    from_member_id: int
    to_member_id: int
    amount_paise: int
    status: str
    payment_provider: str | None
    provider_reference: str | None
    created_at: datetime
    completed_at: datetime | None

