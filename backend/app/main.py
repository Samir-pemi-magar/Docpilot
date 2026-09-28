from fastapi import FastAPI
from app.api.routes import health, version
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging

configure_logging()

settings = get_settings()

app=FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan = lifespan,
)

app.include_router(health.router)
app.include_router(version.router)