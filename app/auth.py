"""JWT (HS256) authentication and role-based permission checks."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.constants import Permission, Role

ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.viewer: {Permission.asset_read},
    Role.contributor: {Permission.asset_read, Permission.asset_write},
    Role.admin: set(Permission),
}

_bearer = HTTPBearer(auto_error=False)


@dataclass
class User:
    id: str
    role: Role


def create_access_token(user_id: str, role: Role, expires_in: int = 3600) -> str:
    """Mint a token. Used by tests / dev tooling; real issuance lives in an auth service."""
    payload = {"sub": user_id, "role": role.value, "exp": int(time.time()) + expires_in}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing credentials")
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return User(id=str(claims["sub"]), role=Role(claims["role"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized from None


def require_permission(permission: Permission) -> Callable[..., User]:
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if permission not in ROLE_PERMISSIONS[user.role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return checker
