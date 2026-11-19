"""Single home for role, permission, status and audit-action strings."""

from enum import StrEnum


class Role(StrEnum):
    admin = "admin"
    contributor = "contributor"
    viewer = "viewer"


class Permission(StrEnum):
    asset_read = "asset:read"
    asset_write = "asset:write"
    asset_delete = "asset:delete"
    asset_approve = "asset:approve"


class AssetStatus(StrEnum):
    pending = "pending"
    active = "active"
    deleted = "deleted"


class AuditAction(StrEnum):
    approve = "approve"
