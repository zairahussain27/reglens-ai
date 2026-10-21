from pydantic import BaseModel, EmailStr, Field

from .models import User

REGULATORS = ["RBI", "SEBI", "IRDAI", "NPCI", "MeitY", "CBIC / GST", "Other"]
DEFAULT_SETTINGS = {"regulators": REGULATORS[:-1], "reminders": True, "changes": True, "weekly": False, "default_lead": 3}


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "workspace_id": u.workspace_id,
            "workspace_name": u.workspace.name, "has_password": bool(u.password_hash), "google": bool(u.google_id)}


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class GoogleIn(BaseModel):
    credential: str


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class PasswordIn(BaseModel):
    current: str = Field(default="", max_length=128)
    new: str = Field(min_length=8, max_length=128)
