import asyncio
import uuid
from typing import Any

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app import search
from app.config import settings
from app.constants import AssetStatus
from app.models import Asset

celery_app = Celery("dam", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(task_serializer="json", result_serializer="json", result_expires=3600)


async def _load_asset(asset_id: str) -> Asset | None:
    # Fresh NullPool engine: each task runs in its own event loop.
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine) as session:
            return await session.get(Asset, uuid.UUID(asset_id))
    finally:
        await engine.dispose()


def _document(asset: Asset) -> dict[str, Any]:
    return {
        "title": asset.title,
        "description": asset.description,
        "tags": [t.tag for t in asset.tags],
        "status": asset.status.value,
        "owner_id": asset.owner_id,
        "original_filename": asset.original_filename,
        "created_at": asset.created_at.isoformat(),
    }


@celery_app.task(name="dam.index_asset", autoretry_for=(search.SearchUnavailableError,),
                 retry_backoff=True, max_retries=5)
def index_asset(asset_id: str) -> str:
    """Push the asset's metadata to OpenSearch (removes it if deleted/missing)."""
    asset = asyncio.run(_load_asset(asset_id))
    if asset is None or asset.status == AssetStatus.deleted:
        search.delete_document(asset_id)
        return "removed"
    search.index_document(asset_id, _document(asset))
    return "indexed"
