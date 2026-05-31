"""Shared Pydantic schemas used by multiple routers."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for schemas that read from ORM rows (enables from_attributes mode)."""

    model_config = ConfigDict(from_attributes=True)


class TimestampedRead(ORMModel):
    """For read schemas that expose created_at / updated_at."""

    created_at: datetime
    updated_at: datetime


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class Page(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    meta: PageMeta


class MessageResponse(BaseModel):
    """Generic success/info envelope."""

    message: str
