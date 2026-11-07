
from pydantic import BaseModel, Field


class AIParseRequest(BaseModel):
    group_id: int = Field(gt=0)
    text: str = Field(min_length=5, max_length=2000)


class AIParseResponse(BaseModel):
    description: str
    amount_paise: int
    paid_by_member_id: int
    participant_ids: list[int]
    split_type: str
