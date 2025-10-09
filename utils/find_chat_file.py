# backend/utils/find_chat_file.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Pattern, Iterable
import re
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

class ChatPatternStrategy(ABC):
    """Interface para estratégias de detecção de padrões em chats"""
    @abstractmethod
    def get_patterns(self) -> List[Pattern]:
        """Retorna lista de padrões regex para identificação de chats"""
        pass

class WhatsAppPatternStrategy(ChatPatternStrategy):
    """Implementação concreta para padrões do WhatsApp"""
    
    @lru_cache(maxsize=1)
    def get_patterns(self) -> List[Pattern]:
        return [
            re.compile(r"\[\d{2}/\d{2}/\d{4}, \d{2}:\d{2}:\d{2}\] ~[A-Za-z0-9]+:"),
            re.compile(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2} - [A-Za-z0-9]+:"),
            re.compile(r"\d{2}/\d{2}/\d{2}, \d{2}:\d{2} - \+[\d\s]+:")
        ]

class TextFileFilter:
    """Responsável pela validação e filtragem de arquivos de texto"""
    
    def __init__(self, allowed_extensions: Iterable[str] = ('.txt',)):
        self.allowed_extensions = tuple(ext.lower() for ext in allowed_extensions)
    
    def filter_valid_files(self, files: Iterable[Path]) -> List[Path]:
        """Filtra arquivos válidos com tratamento de erros"""
        valid_files = []
        for file in files:
            if not self._is_valid_file(file):
                continue
            valid_files.append(file)
        return valid_files
    
    def _is_valid_file(self, file: Path) -> bool:
        """Verifica se um arquivo é válido para processamento"""
        if not isinstance(file, Path):
            logger.warning(f"Tipo de arquivo inválido: {type(file)}")
            return False
        if not file.exists():
            logger.warning(f"Arquivo não encontrado: {file}")
            return False
        if file.suffix.lower() not in self.allowed_extensions:
            return False
        return True

class ChatFileScanner:
    """Responsável pela varredura de arquivos em busca de padrões de chat"""
    
    def __init__(self, pattern_strategy: ChatPatternStrategy):
        self.patterns = pattern_strategy.get_patterns()
    
    def find_chat_file(self, files: Iterable[Path]) -> Optional[Path]:
        """Encontra o arquivo de chat com tratamento robusto de erros"""
        for file in files:
            try:
                if file.name == "_chat.txt" or (len(files) == 1 and file.name.__contains__(".txt")) or self._is_chat_file(file):
                    logger.info(f"Arquivo de chat identificado: {file.name}")
                    return file
            except Exception as e:
                logger.warning(f"Erro ao processar {file.name}: {str(e)}")
                continue
        return None
    
    def _is_chat_file(self, file: Path) -> bool:
        """Verifica se um arquivo contém padrões de chat"""
        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if any(pattern.search(line) for pattern in self.patterns):
                    return True
        return False

class ChatFileFinder:
    """Coordena o processo de descoberta de arquivos de chat"""
    
    def __init__(
        self,
        pattern_strategy: ChatPatternStrategy = None,
        file_filter: TextFileFilter = None,
        file_scanner: ChatFileScanner = None
    ):
        self.pattern_strategy = pattern_strategy or WhatsAppPatternStrategy()
        self.file_filter = file_filter or TextFileFilter()
        self.file_scanner = file_scanner or ChatFileScanner(self.pattern_strategy)
    
    def find_chat_file(self, files: List[Path]) -> Optional[Path]:
        """Interface principal para encontrar arquivo de chat"""
        if not files:
            logger.warning("Lista de arquivos vazia recebida")
            return None
        
        valid_files = self.file_filter.filter_valid_files(files)
        if not valid_files:
            logger.warning("Nenhum arquivo de texto válido encontrado")
            return None
        
        return self.file_scanner.find_chat_file(valid_files)

class ChatFileFinderBuilder:
    """Builder para configuração flexível do ChatFileFinder"""
    
    def __init__(self):
        self._pattern_strategy = WhatsAppPatternStrategy()
        self._file_filter = TextFileFilter()
        self._file_scanner = None
    
    def with_pattern_strategy(self, strategy: ChatPatternStrategy) -> 'ChatFileFinderBuilder':
        self._pattern_strategy = strategy
        return self
    
    def with_file_filter(self, file_filter: TextFileFilter) -> 'ChatFileFinderBuilder':
        self._file_filter = file_filter
        return self
    
    def build(self) -> ChatFileFinder:
        scanner = ChatFileScanner(self._pattern_strategy) if not self._file_scanner else self._file_scanner
        return ChatFileFinder(
            pattern_strategy=self._pattern_strategy,
            file_filter=self._file_filter,
            file_scanner=scanner
        )

# Factory existente (mantida para compatibilidade)
def create_chat_finder() -> ChatFileFinder:
    return ChatFileFinderBuilder().build()
