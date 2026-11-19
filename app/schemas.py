from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class AssetStatus(str, Enum):
    pending = "pending"
    approved = "approved"


class AssetUpload(BaseModel):
    """Metadata accompanying the multipart file upload."""

    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class Asset(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    title: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: AssetStatus
    created_at: datetime


class AssetPage(BaseModel):
    items: list[Asset]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str
