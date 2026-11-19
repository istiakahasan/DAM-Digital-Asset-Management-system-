"""Idempotent provisioning of backing resources."""

import asyncio

from app import search, storage
from app.db import create_tables


async def init_resources() -> None:
    await create_tables()
    await asyncio.to_thread(storage.ensure_bucket)
    await asyncio.to_thread(search.ensure_index)
