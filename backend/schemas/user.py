from uuid import UUID
from typing import Annotated
from pydantic import BaseModel, SecretStr, Field

from ..custom_types import Name
from ..models.project_user import Role


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class UserBase(BaseModel):
    username: Name

    model_config = {"from_attributes": True}


class UserRequest(UserBase):
    password: Annotated[SecretStr, Field(min_length=8, max_length=50)]


class UserResponse(UserBase):
    id: UUID


class MemberResponse(UserBase):
    id: UUID
    role: Role
