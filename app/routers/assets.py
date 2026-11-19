import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import search, storage
from app.access import can_view, search_visibility, sql_visibility
from app.auth import User, require_permission
from app.config import settings
from app.constants import AssetStatus, AuditAction, Permission
from app.db import get_session
from app.models import Asset as AssetRow
from app.models import AssetAudit, AssetTag, IdempotencyKey
from app.schemas import Asset, AssetPage, ErrorResponse
from app.worker import index_asset

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)

Session = Annotated[AsyncSession, Depends(get_session)]


def to_schema(row: AssetRow) -> Asset:
    return Asset(
        id=row.id,
        filename=row.original_filename,
        content_type=row.mime_type,
        size_bytes=row.size_bytes,
        title=row.title,
        description=row.description,
        tags=[t.tag for t in row.tags],
        status=row.status,
        owner_id=row.owner_id,
        rights_expiry=row.rights_expiry,
        created_at=row.created_at,
    )


def enqueue_index(asset_id: uuid.UUID) -> None:
    """Fire-and-forget; an unreachable broker must not fail the request."""
    try:
        index_asset.delay(str(asset_id))
    except Exception:
        logger.exception("Could not enqueue index_asset for %s", asset_id)


async def _find_idempotent(session: AsyncSession, user_id: str, key: str) -> AssetRow | None:
    record = await session.get(IdempotencyKey, (user_id, key))
    if record is None:
        return None
    if record.created_at < datetime.now(UTC) - timedelta(hours=settings.idempotency_ttl_hours):
        await session.delete(record)
        await session.commit()
        return None
    return await session.get(AssetRow, record.asset_id)


@router.post(
    "",
    response_model=Asset,
    operation_id="createAsset",
    responses={413: {"model": ErrorResponse}},
)
async def create_asset(
    session: Session,
    file: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Header(alias="X-Idempotency-Key", min_length=1, max_length=255)],
    user: Annotated[User, Depends(require_permission(Permission.asset_write))],
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    tags: Annotated[list[str] | None, Form()] = None,
    rights_expiry: Annotated[datetime | None, Form()] = None,
) -> Asset:
    if file.size is not None and file.size > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File exceeds the 500MB limit")

    existing = await _find_idempotent(session, user.id, idempotency_key)
    if existing is not None:
        return to_schema(existing)

    asset_id = uuid.uuid4()
    s3_key = f"assets/{asset_id}"
    content_type = file.content_type or "application/octet-stream"
    await run_in_threadpool(storage.upload_fileobj, file.file, s3_key, content_type)

    row = AssetRow(
        id=asset_id,
        original_filename=file.filename or "unnamed",
        mime_type=content_type,
        size_bytes=file.size or 0,
        s3_key=s3_key,
        title=title,
        description=description,
        owner_id=user.id,
        status=AssetStatus.pending,
        rights_expiry=rights_expiry,
        tags=[AssetTag(tag=t) for t in sorted({t.strip() for t in tags or [] if t.strip()})],
    )
    session.add(row)
    session.add(IdempotencyKey(user_id=user.id, key=idempotency_key, asset_id=asset_id))
    try:
        await session.commit()
    except IntegrityError:
        # A concurrent request with the same key won; discard our duplicate upload.
        await session.rollback()
        await run_in_threadpool(storage.delete_object, s3_key)
        winner = await _find_idempotent(session, user.id, idempotency_key)
        if winner is None:
            raise
        return to_schema(winner)

    enqueue_index(asset_id)
    return to_schema(row)


@router.get("", response_model=AssetPage, operation_id="searchAssets",
            responses={503: {"model": ErrorResponse}})
async def search_assets(
    session: Session,
    user: Annotated[User, Depends(require_permission(Permission.asset_read))],
    q: str | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AssetPage:
    if q:
        try:
            ids, total = await run_in_threadpool(
                search.search_ids, q, tags, search_visibility(user), page, page_size
            )
        except search.SearchUnavailableError:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Search backend unavailable"
            ) from None
        by_id: dict[uuid.UUID, AssetRow] = {}
        if ids:
            rows = await session.scalars(
                select(AssetRow).where(
                    AssetRow.id.in_([uuid.UUID(i) for i in ids]), sql_visibility(user)
                )
            )
            by_id = {r.id: r for r in rows}
        items = [to_schema(by_id[uuid.UUID(i)]) for i in ids if uuid.UUID(i) in by_id]
    else:
        conditions = [sql_visibility(user)]
        if tags:
            conditions.append(
                AssetRow.id.in_(select(AssetTag.asset_id).where(AssetTag.tag.in_(tags)))
            )
        total = await session.scalar(select(func.count()).select_from(AssetRow).where(*conditions)) or 0
        rows = await session.scalars(
            select(AssetRow)
            .where(*conditions)
            .order_by(AssetRow.created_at.desc(), AssetRow.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [to_schema(r) for r in rows]
    return AssetPage(items=items, total=total, total_hits=total, page=page, page_size=page_size)


async def _get_asset_or_404(session: AsyncSession, asset_id: uuid.UUID) -> AssetRow:
    row = await session.get(AssetRow, asset_id)
    if row is None or row.status == AssetStatus.deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return row


@router.get("/{id}", response_model=Asset, operation_id="getAsset",
            responses={404: {"model": ErrorResponse}})
async def get_asset(
    id: uuid.UUID,
    session: Session,
    user: Annotated[User, Depends(require_permission(Permission.asset_read))],
) -> Asset:
    row = await _get_asset_or_404(session, id)
    if not can_view(user, row):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return to_schema(row)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteAsset",
               responses={404: {"model": ErrorResponse}})
async def delete_asset(
    id: uuid.UUID,
    user: Annotated[User, Depends(require_permission(Permission.asset_delete))],
) -> None:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Not implemented")


@router.post("/{id}/approve", response_model=Asset, operation_id="approveAsset",
             responses={404: {"model": ErrorResponse}})
async def approve_asset(
    id: uuid.UUID,
    session: Session,
    user: Annotated[User, Depends(require_permission(Permission.asset_approve))],
) -> Asset:
    row = await _get_asset_or_404(session, id)
    if row.status != AssetStatus.active:
        row.status = AssetStatus.active
        session.add(AssetAudit(asset_id=row.id, actor_id=user.id, action=AuditAction.approve.value))
        await session.commit()
        enqueue_index(row.id)
    return to_schema(row)
