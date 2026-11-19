from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status

from app.schemas import Asset, AssetPage, ErrorResponse
from app.security import Permission, User, require_permission

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)

NOT_IMPLEMENTED = HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Not implemented")


@router.post("", response_model=Asset, status_code=status.HTTP_201_CREATED,
             operation_id="createAsset")
def create_asset(
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    tags: Annotated[list[str] | None, Form()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    user: User = Depends(require_permission(Permission.asset_write)),
) -> Asset:
    raise NOT_IMPLEMENTED


@router.get("", response_model=AssetPage, operation_id="searchAssets")
def search_assets(
    q: str | None = None,
    tags: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    user: User = Depends(require_permission(Permission.asset_read)),
) -> AssetPage:
    raise NOT_IMPLEMENTED


@router.get("/{id}", response_model=Asset, operation_id="getAsset",
            responses={404: {"model": ErrorResponse}})
def get_asset(
    id: UUID,
    user: User = Depends(require_permission(Permission.asset_read)),
) -> Asset:
    raise NOT_IMPLEMENTED


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteAsset",
               responses={404: {"model": ErrorResponse}})
def delete_asset(
    id: UUID,
    user: User = Depends(require_permission(Permission.asset_delete)),
) -> None:
    raise NOT_IMPLEMENTED


@router.post("/{id}/approve", response_model=Asset, operation_id="approveAsset",
             responses={404: {"model": ErrorResponse}})
def approve_asset(
    id: UUID,
    user: User = Depends(require_permission(Permission.asset_approve)),
) -> Asset:
    raise NOT_IMPLEMENTED
