# utils/async_file_utils.py - ARQUIVO NOVO E ISOLADO
import aiofiles
from pathlib import Path
from charset_normalizer import from_bytes
from re import Pattern
from typing import List
import logging

logger = logging.getLogger(__name__)

async def async_file_scanner_is_chat_file(file: Path, patterns: List[Pattern]) -> bool:
    """Versão assíncrona do scanner de arquivos"""
    try:
        async with aiofiles.open(file, 'rb') as f:
            content = await f.read()
            result = from_bytes(content).best()
            text_content = str(result) if result else content.decode('utf-8', errors='ignore')
            
            # Verifica padrões de forma não-bloqueante
            return any(pattern.search(text_content) for pattern in patterns)
    except Exception as e:
        logger.warning(f"Erro ao ler arquivo {file}: {str(e)}")
        return False