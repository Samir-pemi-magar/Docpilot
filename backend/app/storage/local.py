import shutil
from pathlib import Path
from typing import BinaryIO

from app.storage.base import StorageService

class LocalStorage(StorageService):
    """Stores files onto local filesystem"""
    
    def __init__ (self,root_dir:str | Path) ->None:
        self.root_dir=Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True,exist_ok=True)
    
    def _get_path(self,storage_key:str) ->Path:
        """Resolve a storage key safely inside the storage directory"""
        if not storage_key or not storage_key.strip():
            raise ValueError("storage Key cannot be empty")
        
        path = (self.root_dir / storage_key).resolve()
        
        try:
            path.relative_to(self.root_dir)
        except ValueError:
            raise ValueError("Storage Key must stay inside the storage directory")
        
        return path
    
    def save(self, file: BinaryIO, storage_key:str) ->None:
        """Save a binary file to local storage"""
        
        path = self._get_path(storage_key)
        path.parent.mkdir(parents=True,exist_ok=True)
        
        with path.open("wb") as destination:
            shutil.copyfileobj(file,destination)
    
    def open(self, storage_key:str) ->BinaryIO:
        """open a stored file for reading"""
        
        path = self._get_path(storage_key)
        return path.open("rb")
    
    def delete(self, storage_key: str) ->None:
        """Delete a stored file if it exists"""
        
        path = self._get_path(storage_key)
        path.unlink(missing_ok=True)
    
    def exists(self, storage_key:str) -> bool:
        """Check wether a stored file exists"""
        
        path = self._get_path(storage_key)
        return path.is_file()
    