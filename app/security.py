"""Mock RBAC. Replace `get_current_user` with real JWT validation later."""

from dataclasses import dataclass
from enum import Enum

from fastapi import Depends, Header, HTTPException, status


class Role(str, Enum):
    viewer = "viewer"
    editor = "editor"
    admin = "admin"


class Permission(str, Enum):
    asset_read = "asset:read"
    asset_write = "asset:write"
    asset_delete = "asset:delete"
    asset_approve = "asset:approve"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.viewer: {Permission.asset_read},
    Role.editor: {Permission.asset_read, Permission.asset_write, Permission.asset_delete},
    Role.admin: set(Permission),
}


@dataclass
class User:
    id: str
    role: Role


def get_current_user(x_mock_role: str | None = Header(default="admin")) -> User:
    """Mock auth: role comes from the X-Mock-Role header (default admin)."""
    try:
        role = Role(x_mock_role)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from None
    return User(id="mock-user", role=role)


def require_permission(permission: Permission):
    def checker(user: User = Depends(get_current_user)) -> User:
        if permission not in ROLE_PERMISSIONS[user.role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
        return user

    return checker
