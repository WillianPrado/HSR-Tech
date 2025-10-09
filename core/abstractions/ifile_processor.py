from abc import ABC, abstractmethod
from fastapi import UploadFile
from typing import Protocol, runtime_checkable
from datetime import datetime
from models.user import User

@runtime_checkable
class IFileProcessor(Protocol):
    """Interface principal para processamento de arquivos"""
    
    @abstractmethod
    async def process_upload(self, file: UploadFile, user: User) -> dict:
        """
        Processa o arquivo recebido conforme regras específicas
        Retorna um dicionário com os dados formatados
        """
        pass

class IFileValidator(ABC):
    """Interface complementar para validações"""
    
    @abstractmethod
    def validate(self, file: UploadFile) -> bool:
        pass