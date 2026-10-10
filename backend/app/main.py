from fastapi import FastAPI

from app.api.routes import chat, conversations, documents, health, organizations, search, version
from app.auth import routes as auth_routes
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging

configure_logging()

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(version.router)
app.include_router(documents.router)
app.include_router(organizations.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(auth_routes.router)
