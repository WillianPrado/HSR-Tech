from abc import ABC, abstractmethod
from pathlib import Path
from fastapi import UploadFile

class StorageProvider(ABC):
    @abstractmethod
    async def save(self, file: UploadFile, destination: Path) -> None:
        pass

    @abstractmethod
    def get_full_path(self, filename: str) -> Path:
        pass

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str = "storage/temp_zips"):
        self.base_path = Path(base_path)

    async def save(self, file: UploadFile, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)

    def get_full_path(self, filename: str) -> Path:
        return self.base_path / filename