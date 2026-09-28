from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

logger = getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Docpilot application starting")
    yield
    logger.info("Docpilot application shutting down")