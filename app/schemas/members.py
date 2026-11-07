
from pydantic import BaseModel, ConfigDict, Field


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=150)


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    email: str | None
    is_active: bool
