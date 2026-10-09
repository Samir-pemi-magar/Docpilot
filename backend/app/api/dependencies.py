from app.core.config import get_settings
from app.storage.local import LocalStorage
from app.storage.base import StorageService

settings = get_settings()

storage = LocalStorage(settings.storage_path)


def get_storage() -> StorageService:
    return storage


def get_document_ingestion_task():
    """Return the background ingestion task; tests can override this."""
    from app.services.ingestion_task import (
        process_document_version_background,
    )

    return process_document_version_background
