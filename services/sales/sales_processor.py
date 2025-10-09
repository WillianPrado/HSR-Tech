from abc import ABC, abstractmethod
from anyio import Path
from fastapi import UploadFile
from datetime import datetime

class SalesProcessor(ABC):
    @abstractmethod
    async def process_upload(self, file: UploadFile) -> dict:
        pass

class BaseSalesProcessor(SalesProcessor):
    def __init__(self, storage_provider):
        self.storage = storage_provider

    async def _save_file(self, file: UploadFile, save_path: Path) -> None:
        await self.storage.save(file, save_path)

    def _base_response(self, filename: str) -> dict:
        return {
            "message": "ZIP em processamento",
            "zip_id": filename,
            "timestamp": datetime.now().isoformat()
        }