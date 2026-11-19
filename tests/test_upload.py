import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import storage
from app.config import settings
from app.constants import AssetStatus, Role
from app.models import Asset, AssetTag
from tests.conftest import PNG_BYTES, auth_headers


async def test_upload_png_persists_rows_and_object(upload, db: AsyncSession) -> None:
    tag = f"tag-{uuid.uuid4().hex[:8]}"
    headers = auth_headers(Role.contributor)
    resp = await upload(
        headers,
        data={
            "title": "Logo",
            "description": "Company logo",
            "tags": [tag, "brand"],
            "rights_expiry": "2030-01-01T00:00:00Z",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    asset_id = uuid.UUID(body["id"])
    assert body["status"] == "pending"
    assert sorted(body["tags"]) == sorted([tag, "brand"])

    row = (await db.scalars(select(Asset).where(Asset.id == asset_id))).one()
    assert row.original_filename == "pic.png"
    assert row.mime_type == "image/png"
    assert row.size_bytes == len(PNG_BYTES)
    assert row.status == AssetStatus.pending
    assert row.rights_expiry is not None and row.rights_expiry.year == 2030
    assert row.s3_key == f"assets/{asset_id}"

    tags = (await db.scalars(select(AssetTag.tag).where(AssetTag.asset_id == asset_id))).all()
    assert sorted(tags) == sorted([tag, "brand"])

    head = await asyncio.to_thread(
        storage.get_client().head_object, Bucket=settings.s3_bucket, Key=row.s3_key
    )
    assert head["ContentLength"] == len(PNG_BYTES)
    assert head["ContentType"] == "image/png"


async def test_idempotency_key_returns_existing_asset(upload, db: AsyncSession) -> None:
    headers = auth_headers(Role.contributor, "idem-user")
    key = uuid.uuid4().hex
    first = await upload(headers, key=key, data={"title": "once"})
    second = await upload(headers, key=key, data={"title": "twice"})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["title"] == "once"

    count = await db.scalar(
        select(func.count()).select_from(Asset).where(Asset.id == uuid.UUID(first.json()["id"]))
    )
    assert count == 1


async def test_missing_idempotency_key_rejected(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/assets",
        headers=auth_headers(Role.contributor),
        files={"file": ("pic.png", PNG_BYTES, "image/png")},
    )
    assert resp.status_code == 422


async def test_oversized_file_rejected_with_413(
    upload, monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    key = uuid.uuid4().hex
    resp = await upload(auth_headers(Role.contributor), key=key)
    assert resp.status_code == 413


async def test_viewer_cannot_upload(upload) -> None:
    resp = await upload(auth_headers(Role.viewer))
    assert resp.status_code == 403
