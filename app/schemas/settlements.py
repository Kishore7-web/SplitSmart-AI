from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SettlementCreate(BaseModel):
    from_member_id: int
    to_member_id: int
    amount_paise: int = Field(gt=0)
    payment_provider: str | None = Field(default="manual", max_length=50)
    provider_reference: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    parent_settlement_id: int | None = None


class SettlementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    from_member_id: int
    to_member_id: int
    from_member_name: str | None = None
    to_member_name: str | None = None
    amount_paise: int
    status: str
    payment_provider: str | None = None
    provider_reference: str | None = None
    notes: str | None = None
    parent_settlement_id: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class SettlementSuggestion(BaseModel):
    from_member_id: int
    from_member_name: str
    to_member_id: int
    to_member_name: str
    amount_paise: int
    from_member_net_balance_paise: int
    to_member_net_balance_paise: int


class GroupSettlementSummary(BaseModel):
    group_id: int
    total_settled_paise: int
    total_pending_paise: int
    pending_count: int
    completed_count: int
    suggestions: list[SettlementSuggestion]
    member_balances: list[dict]
