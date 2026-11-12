import hashlib
import hmac
import os
import secrets
import time
from typing import Any
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.database import get_db
from app.database.models import User, Group, Member, CustomRole, RolePermission


SECRET_KEY = settings.splitsmart_secret_key
TOKEN_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days

# In-memory active session store: token -> {user_id, expires_at}
_active_sessions: dict[str, dict] = {}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, key_hex = hashed_password.split(":")
        test_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(test_key.hex(), key_hex)
    except Exception:
        return False


def create_access_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _active_sessions[token] = {
        "user_id": user_id,
        "expires_at": time.time() + TOKEN_EXPIRY_SECONDS
    }
    return token


def invalidate_access_token(token: str):
    _active_sessions.pop(token, None)


def get_optional_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
) -> User | None:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        return None

    sess = _active_sessions.get(token)
    if not sess or sess["expires_at"] < time.time():
        _active_sessions.pop(token, None)
        return None

    user = db.get(User, sess["user_id"])
    if not user or not user.is_active:
        return None

    return user


def get_current_user(
    user: User | None = Depends(get_optional_current_user)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def check_group_permission(
    db: Session,
    group_id: int,
    user: Any,
    required_permission: str | None = None
) -> Member | None:
    """
    Checks if user is authorized to perform action on group.
    In unauthenticated / guest mode or test mode (user is not a User instance), allows action,
    while in authenticated mode verifies user is a member of the group and has permissions.
    """
    if not isinstance(user, User):
        return None

    member = db.query(Member).filter(
        Member.group_id == group_id,
        Member.user_id == user.id,
        Member.is_active.is_(True)
    ).first()

    if not member and not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an authorized member of this group."
        )

    if member and member.role == "owner":
        return member

    if required_permission and member:
        # Check custom role permissions if assigned
        if member.custom_role_id:
            perm = db.query(RolePermission).filter(
                RolePermission.role_id == member.custom_role_id,
                RolePermission.permission_key == required_permission
            ).first()
            if not perm and member.role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: '{required_permission}'."
                )

    return member


def ensure_owner_retention(db: Session, group_id: int, target_member_id: int, new_role: str | None = None, is_deleting: bool = False):
    """
    Ensures that every active group retains at least one active owner.
    Prevents removing or demoting the last owner.
    """
    target = db.get(Member, target_member_id)
    if not target or target.group_id != group_id:
        return

    if target.role == "owner":
        owner_count = db.query(Member).filter(
            Member.group_id == group_id,
            Member.role == "owner",
            Member.is_active.is_(True)
        ).count()

        if owner_count <= 1:
            if is_deleting or (new_role and new_role != "owner"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove or demote the last remaining owner of the group. Transfer ownership first."
                )
