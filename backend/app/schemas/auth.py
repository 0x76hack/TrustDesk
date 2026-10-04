from pydantic import BaseModel, Field
from typing import Optional


class UserResponse(BaseModel):
    id: str
    username: str
    name: str
    email: str
    role: str
    phone: Optional[str] = None
    mfa_setup_completed: bool = False
    is_primary_admin: bool = False
    is_active: bool = True

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str
    code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserCreate(BaseModel):
    username: str
    name: str
    email: str
    password: str
    role: str = "agent"
    phone: Optional[str] = None
    is_active: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class MfaChallengeResponse(BaseModel):
    mfa_required: bool = True
    mfa_setup_required: bool = False
    mfa_token: str
    username: str
    current_email: Optional[str] = None
    current_phone: Optional[str] = None
    expires_in_seconds: int = 120
    message: str = "Multi-Factor Authentication required. Enter 6-digit verification code."


class MfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str


class MfaSetupSendOtpRequest(BaseModel):
    setup_token: str
    email: str
    phone: Optional[str] = None


class MfaSetupVerifyOtpRequest(BaseModel):
    setup_token: str
    email: str
    phone: Optional[str] = None
    code: str


class MfaResendLoginOtpRequest(BaseModel):
    mfa_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class OAuthLoginRequest(BaseModel):
    provider: str = "corporate_sso"
    email: str
    state: Optional[str] = None
    code_verifier: Optional[str] = None


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class PrimaryAdminSetupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=5, max_length=200)
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = None
    code: Optional[str] = None
