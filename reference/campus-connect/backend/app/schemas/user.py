from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.models import UserRole

class SignupRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    full_name: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)
    confirm_password: str = Field(..., min_length=8, max_length=255)
    role: UserRole

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_full_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("password and confirm password do not match")
        return self

class SignupResponse(BaseModel):
    access_token: str
    refresh_token: str
    message: str

class LoginRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    message: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

class ForgotPasswordResponse(BaseModel):
    message: str

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, max_length=255)
    confirm_password: str = Field(..., min_length=8, max_length=255)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("password and confirm password do not match")
        return self

class ResetPasswordResponse(BaseModel):
    message: str

class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., min_length=1)
    intent: Literal["login", "signup"] = "login"

class GoogleAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    is_new_user: bool
    message: str
