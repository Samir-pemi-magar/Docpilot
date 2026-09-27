from fastapi import FastAPI
from app.api.routes import health
from app.core.config import settings

app=FastAPI(
    title=settings.app_name,
    version=settings.app_version
)

app.include_router(health.router)