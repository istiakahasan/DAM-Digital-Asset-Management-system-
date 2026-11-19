"""Row-level visibility rules shared by Postgres and OpenSearch queries."""

from typing import Any

from sqlalchemy import ColumnElement, and_, or_

from app.auth import User
from app.constants import AssetStatus, Role
from app.models import Asset


def can_view(user: User, asset: Asset) -> bool:
    if asset.status == AssetStatus.deleted:
        return False
    if user.role == Role.admin:
        return True
    if asset.status == AssetStatus.active:
        return True
    return user.role == Role.contributor and asset.owner_id == user.id


def sql_visibility(user: User) -> ColumnElement[bool]:
    not_deleted = Asset.status != AssetStatus.deleted
    if user.role == Role.admin:
        return not_deleted
    if user.role == Role.contributor:
        return and_(
            not_deleted, or_(Asset.status == AssetStatus.active, Asset.owner_id == user.id)
        )
    return Asset.status == AssetStatus.active


def search_visibility(user: User) -> dict[str, Any]:
    """OpenSearch bool clause equivalent of `sql_visibility`."""
    not_deleted = {"term": {"status": AssetStatus.deleted.value}}
    active = {"term": {"status": AssetStatus.active.value}}
    if user.role == Role.admin:
        return {"bool": {"must_not": [not_deleted]}}
    if user.role == Role.contributor:
        return {
            "bool": {
                "must_not": [not_deleted],
                "should": [active, {"term": {"owner_id": user.id}}],
                "minimum_should_match": 1,
            }
        }
    return {"bool": {"filter": [active]}}
