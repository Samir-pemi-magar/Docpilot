from abc import ABC, abstractmethod
from typing import BinaryIO

class StorageService(ABC):
    """Abstract interface for file storage backends"""
    
    @abstractmethod
    def save(
        self,
        file:BinaryIO,
        storage_key: str,
    ) ->None:
        """Save a file using given storage key"""
        raise NotImplementedError
    
    @abstractmethod
    def open(
        self,
        storage_key: str,
    )->BinaryIO:
        """Open a stored file for reading"""
        raise NotImplementedError
    
    @abstractmethod
    def delete(
        self,
        storage_key: str,
    ) -> None:
        """Delete a stored file."""
        raise NotImplementedError

    @abstractmethod
    def exists(
        self,
        storage_key: str,
    ) -> bool:
        """Check whether a stored file exists."""
        raise NotImplementedError