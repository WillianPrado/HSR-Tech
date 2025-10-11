# backend/services/zip/zip_extractor.py - VERSÃO CORRIGIDA
from abc import ABC, abstractmethod
from pathlib import Path
import zipfile
import asyncio
from typing import List
import logging
import aiofiles
import io

logger = logging.getLogger(__name__)

class ExtractionStrategy(ABC):
    @abstractmethod
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        pass

class TrueAsyncZipExtractorStrategy(ExtractionStrategy):
    """Estratégia verdadeiramente assíncrona usando threads para operações bloqueantes"""
    
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """Extrai ZIP de forma não-bloqueante usando threads"""
        return await asyncio.to_thread(self._extract_sync, zip_path, output_dir)
    
    def _extract_sync(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """Versão síncrona executada em thread separada"""
        extracted_files = []
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extrai tudo de uma vez (mais eficiente)
                zip_ref.extractall(output_dir)
                
                # Coleta paths dos arquivos extraídos
                for zip_info in zip_ref.infolist():
                    if not zip_info.is_dir():
                        extracted_path = (output_dir / zip_info.filename).resolve()
                        if extracted_path.exists():
                            extracted_files.append(extracted_path)
            
            logger.info(f"Extraídos {len(extracted_files)} arquivos de {zip_path.name}")
            return extracted_files
            
        except zipfile.BadZipFile as e:
            logger.error(f"ZIP inválido: {zip_path.name} - {str(e)}")
            raise ValueError(f"ZIP inválido: {zip_path.name}") from e
        except Exception as e:
            logger.error(f"Erro ao extrair {zip_path.name}: {str(e)}")
            raise

class AsyncZipExtractorStrategy(ExtractionStrategy):
    """Estratégia alternativa - processamento arquivo por arquivo"""
    
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        """Extrai cada arquivo individualmente de forma assíncrona"""
        extracted_files = []
        
        # Abre o ZIP uma vez e processa cada arquivo
        def get_zip_contents():
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                return [
                    (zip_info, zip_ref.open(zip_info).read())
                    for zip_info in zip_ref.infolist()
                    if not zip_info.is_dir()
                ]
        
        # Executa a leitura do ZIP em thread
        zip_contents = await asyncio.to_thread(get_zip_contents)
        
        # Escreve cada arquivo de forma assíncrona
        for zip_info, content in zip_contents:
            full_path = output_dir / zip_info.filename
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(full_path, 'wb') as target_file:
                await target_file.write(content)
            
            extracted_files.append(full_path)
        
        logger.info(f"Extraídos {len(extracted_files)} arquivos de {zip_path.name}")
        return extracted_files

class AsyncZipExtractor:
    """Main extractor - usa estratégia otimizada por padrão"""
    
    def __init__(self, strategy: ExtractionStrategy = None):
        # ✅ Usa estratégia que move TODO o processamento para thread
        self.strategy = strategy or TrueAsyncZipExtractorStrategy()
    
    async def extract(self, zip_path: Path, output_dir: Path) -> List[Path]:
        self._validate_paths(zip_path, output_dir)
        extracted_files = await self.strategy.extract(zip_path, output_dir)
        
        # Filtra arquivos relevantes (mantenha sua lógica)
        audio_files = [
            f for f in extracted_files 
            if f.suffix.lower() in ('.opus', '.mp3', '.wav', '.ogg', '.m4a', '.txt')
        ]
        
        logger.info(f"Arquivos de processamento: {len(audio_files)}/{len(extracted_files)}")
        return audio_files
    
    def _validate_paths(self, zip_path: Path, output_dir: Path) -> None:
        if not zip_path.exists():
            raise FileNotFoundError(f"Arquivo ZIP não encontrado: {zip_path}")
        if not zip_path.is_file():
            raise ValueError(f"Caminho não é um arquivo: {zip_path}")
        output_dir.mkdir(parents=True, exist_ok=True)