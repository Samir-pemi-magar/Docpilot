from fastapi import FastAPI
from app.api.routes import health, version
from app.core.config import get_settings

settings = get_settings()

app=FastAPI(
    title=settings.app_name,
    version=settings.app_version
)

app.include_router(health.router)
app.include_router(version.router)