from typing import Any
from pydantic import BaseModel, Field


class AIParseRequest(BaseModel):
    group_id: int = Field(gt=0)
    text: str = Field(min_length=3, max_length=5000)
    current_member_id: int | None = None


class AIParseResponse(BaseModel):
    description: str
    amount_paise: int
    paid_by_member_id: int | None = None
    payer_name: str | None = None
    participant_ids: list[int] = []
    participant_names: list[str] = []
    split_type: str = "equal"
    category: str = "General"
    merchant: str | None = None
    confidence: float = 1.0
    missing_fields: list[str] = []
    clarification_prompt: str | None = None


class AIDraftExpenseConfirm(BaseModel):
    group_id: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=300)
    total_amount_paise: int = Field(gt=0)
    paid_by_member_id: int
    participant_ids: list[int] = Field(min_length=1)
    split_type: str = Field(default="equal", pattern="^(equal|custom|percentage)$")
    category: str = Field(default="General", max_length=50)
    activity_id: int | None = None
    merchant: str | None = None
    notes: str | None = None
    evidence_id: int | None = None


class AIChatRequest(BaseModel):
    group_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=2000)


class AIChatResponse(BaseModel):
    reply: str
    sources: list[str] = []
    grounded_data: dict[str, Any] = {}
    suggested_actions: list[dict[str, Any]] = []


class AIGroupProposalRequest(BaseModel):
    description: str = Field(min_length=5, max_length=4000)


class AIGroupRefineRequest(BaseModel):
    current_proposal: dict[str, Any]
    instruction: str = Field(min_length=2, max_length=1000)


class AIGroupConfirmRequest(BaseModel):
    structure: dict[str, Any]


class AIToolExecuteRequest(BaseModel):
    tool_name: str
    tool_args: dict[str, Any]
