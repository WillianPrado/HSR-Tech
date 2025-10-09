# interfaces/iprocessor.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

from fastapi import UploadFile



class IStatusTracker(ABC):
    @abstractmethod
    async def update(self, identifier: str, message: str, progress: float):
        pass

class IFileExtractor(ABC):
    @abstractmethod
    async def extract(self, zip_path: Path, output_dir: Path) -> list[Path]:
        pass

class IFileFinder(ABC):
    @abstractmethod
    def find_file(self, files: list[Path]) -> Optional[Path]:
        pass