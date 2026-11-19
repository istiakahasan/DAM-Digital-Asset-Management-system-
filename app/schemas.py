from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.constants import AssetStatus


class Asset(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: AssetStatus
    owner_id: str
    rights_expiry: datetime | None = None
    created_at: datetime


class AssetPage(BaseModel):
    items: list[Asset]
    total: int
    total_hits: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str
