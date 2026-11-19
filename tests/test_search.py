import uuid

import httpx
import pytest
from celery.result import AsyncResult
from opensearchpy import OpenSearch
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app import search
from app.constants import AssetStatus, Role
from app.models import Asset
from app.worker import index_asset
from tests.conftest import auth_headers


def wait_for_indexing(results: list[AsyncResult]) -> None:
    for result in results:
        assert result.get(timeout=10) == "indexed"


async def upload_three(upload, unique_tag: str, owner: dict[str, str]) -> list[str]:
    ids = []
    for n in range(3):
        # Only the first asset carries the unique tag; all share the common one.
        tags = ["shared-tag"] + ([unique_tag] if n == 0 else [])
        resp = await upload(owner, data={"title": f"asset {n}", "tags": tags})
        assert resp.status_code == 200, resp.text
        ids.append(resp.json()["id"])
    return ids


async def test_search_by_unique_tag_returns_one_hit(
    client: httpx.AsyncClient, upload, index_results: list[AsyncResult]
) -> None:
    unique = f"uniq-{uuid.uuid4().hex}"
    admin = auth_headers(Role.admin)
    ids = await upload_three(upload, unique, auth_headers(Role.contributor))
    wait_for_indexing(index_results)

    resp = await client.get("/assets", params={"q": unique}, headers=admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_hits"] == 1
    assert [i["id"] for i in body["items"]] == [ids[0]]


async def test_search_matches_title_and_description(
    client: httpx.AsyncClient, upload, index_results: list[AsyncResult]
) -> None:
    word = f"zebra{uuid.uuid4().hex[:10]}"
    owner = auth_headers(Role.contributor)
    await upload(owner, data={"title": f"A {word} photo"})
    await upload(owner, data={"description": f"contains {word} too"})
    wait_for_indexing(index_results)

    resp = await client.get("/assets", params={"q": word}, headers=auth_headers(Role.admin))
    assert resp.json()["total_hits"] == 2


async def test_deleted_assets_never_appear(
    client: httpx.AsyncClient, upload, db: AsyncSession, index_results: list[AsyncResult]
) -> None:
    unique = f"gone-{uuid.uuid4().hex}"
    resp = await upload(auth_headers(Role.contributor), data={"tags": [unique]})
    asset_id = resp.json()["id"]
    wait_for_indexing(index_results)
    admin = auth_headers(Role.admin)
    assert (await client.get("/assets", params={"q": unique}, headers=admin)).json()["total_hits"] == 1

    await db.execute(
        update(Asset).where(Asset.id == uuid.UUID(asset_id)).values(status=AssetStatus.deleted)
    )
    await db.commit()
    # Even before re-indexing, the DB re-check hides the deleted row from results.
    stale = await client.get("/assets", params={"q": unique}, headers=admin)
    assert stale.json()["items"] == []
    # Re-index removes it from OpenSearch entirely.
    assert index_asset.delay(asset_id).get(timeout=10) == "removed"
    fresh = await client.get("/assets", params={"q": unique}, headers=admin)
    assert fresh.json()["total_hits"] == 0

    listing = await client.get("/assets", params={"page_size": 100}, headers=admin)
    assert asset_id not in [i["id"] for i in listing.json()["items"]]


async def test_listing_without_q_uses_postgres(client: httpx.AsyncClient, upload) -> None:
    tag = f"list-{uuid.uuid4().hex}"
    owner = auth_headers(Role.contributor)
    await upload(owner, data={"tags": [tag]})
    resp = await client.get("/assets", params={"tags": tag}, headers=auth_headers(Role.admin))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


async def test_opensearch_down_returns_503(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = OpenSearch(hosts=["http://127.0.0.1:1"], timeout=1, max_retries=0)
    monkeypatch.setattr(search, "get_client", lambda: dead)
    resp = await client.get("/assets", params={"q": "anything"}, headers=auth_headers(Role.admin))
    assert resp.status_code == 503
    assert resp.json()["detail"] == "Search backend unavailable"
