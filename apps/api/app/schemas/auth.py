from pydantic import BaseModel, Field, field_validator, model_validator


def clean_email(value: str) -> str:
    cleaned = value.strip().lower()
    if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@") or len(cleaned) > 320:
        raise ValueError("Enter a valid work email.")
    return cleaned


def validate_password_strength(value: str) -> str:
    if not any(char.islower() for char in value) or not any(char.isupper() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("Password must include uppercase, lowercase, and a number.")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str
    password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)
    organisation_name: str = Field(..., min_length=2, max_length=255)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return clean_email(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1, max_length=128)
    remember: bool = False

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return clean_email(value)


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return clean_email(value)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=24, max_length=256)
    password: str = Field(..., min_length=12, max_length=128)
    confirm_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password_strength(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=24, max_length=256)


class AuthUserRead(BaseModel):
    id: str
    email: str
    full_name: str | None
    status: str
    email_verified: bool
    onboarding_complete: bool


class AuthOrganisationRead(BaseModel):
    name: str
    slug: str
    plan_key: str
    status: str


class AuthWorkspaceRead(BaseModel):
    name: str
    slug: str
    status: str


class AuthMembershipRead(BaseModel):
    role: str
    status: str


class AuthContextRead(BaseModel):
    user: AuthUserRead
    organisation: AuthOrganisationRead
    workspace: AuthWorkspaceRead
    membership: AuthMembershipRead
    organisation_id: str
    workspace_id: str
    role: str
    onboarding_complete: bool


class AuthMessageRead(BaseModel):
    message: str
    reset_delivery_supported: bool = False
