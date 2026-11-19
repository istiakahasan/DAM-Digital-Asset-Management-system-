import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import assets
from app.startup import init_resources

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        await init_resources()
    except Exception:
        logger.exception("Resource provisioning failed; continuing without it")
    yield


app = FastAPI(title="DAM API", version="0.1.0", lifespan=lifespan)
app.include_router(assets.router)
