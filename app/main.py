from fastapi import FastAPI

from app.routers import assets

app = FastAPI(title="DAM API", version="0.1.0")
app.include_router(assets.router)
