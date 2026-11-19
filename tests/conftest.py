"""Integration fixtures. Requires `docker compose up -d` (postgres, redis, opensearch, minio)."""

import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from celery.contrib.testing.worker import start_worker
from celery.result import AsyncResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token
from app.constants import Role
from app.db import SessionLocal
from app.main import app
from app.startup import init_resources
from app.worker import celery_app, index_asset

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def provisioned_services() -> None:
    await init_resources()


@pytest.fixture(scope="session", autouse=True)
def celery_worker() -> Iterator[None]:
    """Run a real Celery worker (solo pool) in a background thread."""
    with start_worker(celery_app, perform_ping_check=False, pool="solo", loglevel="WARNING"):
        yield


@pytest_asyncio.fixture(loop_scope="session")
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(loop_scope="session")
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@pytest.fixture
def index_results(monkeypatch: pytest.MonkeyPatch) -> list[AsyncResult]:
    """Capture the AsyncResult of every `index_asset.delay()` so tests can `.get()` it."""
    results: list[AsyncResult] = []
    original = index_asset.delay

    def capturing_delay(*args: Any, **kwargs: Any) -> AsyncResult:
        result = original(*args, **kwargs)
        results.append(result)
        return result

    monkeypatch.setattr(index_asset, "delay", capturing_delay)
    return results


def auth_headers(role: Role, user_id: str | None = None) -> dict[str, str]:
    token = create_access_token(user_id or f"{role.value}-{uuid.uuid4().hex[:8]}", role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def upload(client: httpx.AsyncClient) -> Callable[..., Any]:
    async def _upload(
        headers: dict[str, str],
        *,
        key: str | None = None,
        data: dict[str, Any] | None = None,
        content: bytes = PNG_BYTES,
        filename: str = "pic.png",
    ) -> httpx.Response:
        return await client.post(
            "/assets",
            headers={**headers, "X-Idempotency-Key": key or uuid.uuid4().hex},
            files={"file": (filename, content, "image/png")},
            data=data or {},
        )

    return _upload
