from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_token


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Please sign in")
    uid = decode_token(authorization[7:].strip())
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(401, "Please sign in")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    # Admin access is intentionally reserved for the designated account.
    if user.email.lower() != "zairahussain27@gmail.com":
        raise HTTPException(403, "Only the designated administrator can do this")
    return user
