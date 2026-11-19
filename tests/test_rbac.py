import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import AuditAction, Role
from app.models import AssetAudit
from tests.conftest import auth_headers


async def test_viewer_blocked_from_pending_then_allowed_after_approval(
    client: httpx.AsyncClient, upload, db: AsyncSession
) -> None:
    created = await upload(auth_headers(Role.contributor), data={"title": "secret"})
    asset_id = created.json()["id"]
    viewer = auth_headers(Role.viewer)
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"
    admin = auth_headers(Role.admin, admin_id)

    assert (await client.get(f"/assets/{asset_id}", headers=viewer)).status_code == 403

    approved = await client.post(f"/assets/{asset_id}/approve", headers=admin)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "active"

    audit = (
        await db.scalars(select(AssetAudit).where(AssetAudit.asset_id == uuid.UUID(asset_id)))
    ).all()
    assert len(audit) == 1
    assert audit[0].actor_id == admin_id
    assert audit[0].action == AuditAction.approve.value
    assert audit[0].timestamp is not None

    assert (await client.get(f"/assets/{asset_id}", headers=viewer)).status_code == 200


async def test_contributor_sees_own_pending_but_not_others(client: httpx.AsyncClient, upload) -> None:
    owner = auth_headers(Role.contributor, f"owner-{uuid.uuid4().hex[:6]}")
    other = auth_headers(Role.contributor, f"other-{uuid.uuid4().hex[:6]}")
    asset_id = (await upload(owner)).json()["id"]
    assert (await client.get(f"/assets/{asset_id}", headers=owner)).status_code == 200
    assert (await client.get(f"/assets/{asset_id}", headers=other)).status_code == 403
    assert (await client.get(f"/assets/{asset_id}", headers=auth_headers(Role.admin))).status_code == 200


async def test_only_admin_can_approve(client: httpx.AsyncClient, upload) -> None:
    owner = auth_headers(Role.contributor)
    asset_id = (await upload(owner)).json()["id"]
    for role in (Role.contributor, Role.viewer):
        resp = await client.post(f"/assets/{asset_id}/approve", headers=auth_headers(role))
        assert resp.status_code == 403


async def test_missing_or_bad_token_is_401(client: httpx.AsyncClient) -> None:
    asset_id = uuid.uuid4()
    assert (await client.get(f"/assets/{asset_id}")).status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert (await client.get(f"/assets/{asset_id}", headers=bad)).status_code == 401


async def test_listing_hides_pending_from_viewers(client: httpx.AsyncClient, upload) -> None:
    tag = f"vis-{uuid.uuid4().hex}"
    await upload(auth_headers(Role.contributor), data={"tags": [tag]})
    viewer = await client.get("/assets", params={"tags": tag}, headers=auth_headers(Role.viewer))
    admin = await client.get("/assets", params={"tags": tag}, headers=auth_headers(Role.admin))
    assert viewer.json()["total"] == 0
    assert admin.json()["total"] == 1
