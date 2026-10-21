from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import current_user
from ..models import User, Workspace
from ..schemas import DEFAULT_SETTINGS, GoogleIn, LoginIn, PasswordIn, ProfileIn, SignupIn, user_out
from ..security import create_token, hash_password, login_limiter, verify_password

router = APIRouter()
settings = get_settings()


def _session(user: User) -> dict:
    return {"token": create_token(user.id), "user": user_out(user)}


def _new_user(db: Session, name: str, email: str, **extra) -> User:
    normalized_email = email.strip().lower()
    ws = Workspace(name=f"{name.split()[0]}'s workspace" if name.strip() else "My workspace", settings=dict(DEFAULT_SETTINGS))
    db.add(ws)
    db.flush()
    user = User(name=name.strip(), email=normalized_email,
                role="admin" if normalized_email == "zairahussain27@gmail.com" else "user",
                workspace_id=ws.id, **extra)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/config")
def config():
    return {"google_client_id": settings.google_client_id or None}


@router.post("/auth/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    return _session(_new_user(db, body.name, body.email, password_hash=hash_password(body.password)))


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    key = f"{body.email.lower()}|{request.client.host if request.client else ''}"
    login_limiter.check(key)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        login_limiter.hit(key)
        if user and not user.password_hash:
            raise HTTPException(401, "This account uses Google sign-in. Use the Google button instead.")
        raise HTTPException(401, "Incorrect email or password")
    login_limiter.reset(key)
    return _session(user)


@router.post("/auth/google")
def google(body: GoogleIn, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured")
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token
        info = id_token.verify_oauth2_token(body.credential, g_requests.Request(), settings.google_client_id)
    except Exception:
        raise HTTPException(401, "Google sign-in could not be verified")
    if not info.get("email_verified"):
        raise HTTPException(401, "Your Google email is not verified")
    email, sub = info["email"].lower(), info["sub"]
    user = db.scalar(select(User).where((User.google_id == sub) | (User.email == email)))
    if user:
        if not user.google_id:
            user.google_id = sub
            db.commit()
    else:
        user = _new_user(db, info.get("name") or email.split("@")[0], email, google_id=sub)
    return _session(user)


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.put("/auth/me")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = body.name.strip()
    db.commit()
    return user_out(user)


@router.post("/auth/password")
def change_password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.password_hash and not verify_password(body.current, user.password_hash):
        raise HTTPException(400, "Your current password is incorrect")
    user.password_hash = hash_password(body.new)
    db.commit()
    return {"ok": True}
