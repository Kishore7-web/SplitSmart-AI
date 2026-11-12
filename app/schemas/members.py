from pydantic import BaseModel, ConfigDict, Field


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    role: str = Field(default="member", max_length=50)
    custom_role_id: int | None = None
    user_id: int | None = None


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    role: str | None = Field(default=None, max_length=50)
    custom_role_id: int | None = None
    user_id: int | None = None
    is_active: bool | None = None


class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    name: str
    email: str | None = None
    phone: str | None = None
    role: str = "member"
    custom_role_id: int | None = None
    user_id: int | None = None
    is_active: bool = True
