from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

from app.core.config import get_settings
from app.storage.local import LocalStorage

logger = getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    app.state.storage = LocalStorage(settings.storage_path)
    
    logger.info("Docpilot application starting")
    logger.info("Storage path: %s", settings.storage_path)
    
    yield
    
    logger.info("Docpilot application shutting down")