from app.core.config import get_settings
from app.storage.local import LocalStorage
from app.storage.base import StorageService

settings = get_settings()

storage = LocalStorage(settings.storage_path)


def get_storage() -> StorageService:
    return storage
