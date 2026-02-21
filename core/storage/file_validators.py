from fastapi import HTTPException, UploadFile
from pathlib import Path
import re

class FileValidator:
    @staticmethod
    def validate_zip_extension(filename: str) -> None:
        if not filename.lower().endswith('.zip'):
            raise HTTPException(400, "Only .zip files are allowed")

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove caracteres especiais e previne path traversal"""
        sanitized = re.sub(r'[^\w.-]', '_', filename)
        if '..' in sanitized or sanitized.startswith('/'):
            raise HTTPException(400, "Invalid filename")
        return sanitized

    @staticmethod
    def validate_file_size(file: UploadFile, max_size_mb: int = 500) -> None:
        max_bytes = max_size_mb * 1024 * 1024
        if file.size > max_bytes:
            raise HTTPException(400, f"File exceeds maximum size of {max_size_mb}MB")