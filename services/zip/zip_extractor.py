# backend/services/zip/zip_extractor.py
from abc import ABC, abstractmethod
from pathlib import Path
import zipfile
import asyncio
from typing import List
import logging
import os

logger = logging.getLogger(__name__)

class ExtractionStrategy(ABC):
    """Abstract base class for extraction strategies"""
    @abstractmethod
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """Extract zip contents to output directory"""
        pass

class DefaultZipExtractor(ExtractionStrategy):
    """Default ZIP extraction implementation"""
    
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """
        Extract all files from ZIP archive while preserving full directory structure
        Returns list of absolute paths to all extracted files
        """
        try:
            extracted_files = []
            
            # Cria diretório de extração se não existir
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extrai mantendo toda a estrutura de diretórios
                zip_ref.extractall(output_dir)
                
                # Obtém todos os arquivos extraídos (ignorando diretórios)
                for zip_info in zip_ref.infolist():
                    if not zip_info.is_dir():
                        # Constrói o caminho completo normalizado
                        extracted_path = (output_dir / zip_info.filename).resolve()
                        
                        # Verifica se o arquivo realmente existe
                        if not extracted_path.exists():
                            logger.warning(f"Arquivo extraído não encontrado no local esperado: {extracted_path}")
                            continue
                            
                        extracted_files.append(extracted_path)
                
                logger.info(f"Extraídos {len(extracted_files)} arquivos de {zip_path.name}")
                logger.debug(f"Arquivos extraídos: {extracted_files}")
                
                return extracted_files
                
        except zipfile.BadZipFile as e:
            logger.error(f"ZIP inválido: {zip_path.name} - {str(e)}")
            raise ValueError(f"ZIP inválido: {zip_path.name}") from e
        except Exception as e:
            logger.error(f"Erro ao extrair {zip_path.name}: {str(e)}")
            raise

class AsyncZipExtractor:
    """Main extractor class following Dependency Inversion Principle"""
    
    def __init__(self, strategy: ExtractionStrategy = None):
        self.strategy = strategy or DefaultZipExtractor()
    
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """
        Public interface for async extraction
        Returns list of absolute paths to all extracted files
        """
        self._validate_paths(zip_path, output_dir)
        
        # Extrai os arquivos
        extracted_files = await self.strategy.extract(zip_path, output_dir)
        
        # Filtra apenas arquivos de áudio (opcional)
        audio_files = [
            f for f in extracted_files 
            if f.suffix.lower() in ('.opus', '.mp3', '.wav', '.ogg', '.m4a', '.txt')
        ]
        
        logger.info(f"Arquivos de áudio extraídos: {len(audio_files)}/{len(extracted_files)}")
        return audio_files  # Ou retorne todos os arquivos se preferir
    
    def _validate_paths(self, zip_path: Path, output_dir: Path) -> None:
        """Validate input paths before processing"""
        if not zip_path.exists():
            raise FileNotFoundError(f"Arquivo ZIP não encontrado: {zip_path}")
        if not zip_path.is_file():
            raise ValueError(f"Caminho não é um arquivo: {zip_path}")
        
        # Cria o diretório de saída se não existir
        output_dir.mkdir(parents=True, exist_ok=True)