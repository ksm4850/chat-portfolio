import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from src.shared.schema import CamelModel


def normalize_email(email: str) -> str:
    """대소문자만 다른 이메일을 같은 계정으로 본다. 저장·조회 전에 항상 거친다."""
    return email.strip().lower()


NormalizedEmail = Annotated[EmailStr, AfterValidator(normalize_email)]


class UserCreate(CamelModel):
    email: NormalizedEmail
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)


class UserUpdate(CamelModel):
    """본인이 바꿀 수 있는 항목."""

    full_name: str | None = Field(default=None, max_length=120)


class UserAdminUpdate(UserUpdate):
    """관리자만 바꿀 수 있는 항목까지 포함한다."""

    is_active: bool | None = None


class PasswordUpdate(CamelModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserRead(CamelModel):
    """응답 전용 모델. `hashedPassword` 는 절대 포함하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class UserPage(CamelModel):
    items: list[UserRead]
    total_count: int
    offset: int
    limit: int


class UserAuthState(BaseModel):
    """인증 모듈에 넘기는 내부 전용 값. 응답 모델로 쓰지 않는다."""

    user: UserRead
    token_version: int
