# backend\core\tasks.py
from pathlib import Path
from services.zip.zip_extractor import AsyncZipExtractor
from services.chat.chat_file_handler import ChatProcessor
from services.audio.openai_transcriber import OpenAITranscriber
from services.reports.coach_analyzer import process_conversation_to_pdf
from utils.find_chat_file import create_chat_finder, ChatFileFinder  # Import corrigido
from utils.file_cleaner import clean_extracted_files
import os
import logging
import asyncio
from typing import Dict, Optional, List
from abc import ABC, abstractmethod
import aiofiles
from core.status_tracker import set_status
from charset_normalizer import from_bytes

logger = logging.getLogger(__name__)

# Interface para tracking de status
class StatusTracker(ABC):
    @abstractmethod
    async def update(self, zip_id: str, message: str, progress: float):
        pass

class DatabaseStatusTracker(StatusTracker):
    async def update(self, zip_id: str, message: str, progress: float):
        await set_status(zip_id, message, progress)

# Classe para processamento de áudio
class AudioProcessor:
    def __init__(self, transcriber: OpenAITranscriber):
        self.transcriber = transcriber
    
    async def process_audio(self, audio_path: Path) -> str:
        return await asyncio.to_thread(
            self.transcriber.transcribe, 
            str(audio_path)
        )

# Classe principal de processamento
class ZipProcessingPipeline:
    def __init__(
        self,
        extractor: AsyncZipExtractor,
        chat_finder: ChatFileFinder, 
        transcriber: OpenAITranscriber,
        status_tracker: StatusTracker
    ):
        self.extractor = extractor
        self.chat_finder = chat_finder
        self.transcriber = transcriber
        self.tracker = status_tracker

    async def execute(self, zip_path: Path) -> Dict[str, Optional[str]]:
        base_dir = Path("storage")
        output_dir = base_dir / "output"
        zip_id = zip_path.name
        
        try:
            await self._process_zip_file(zip_path, output_dir, zip_id)
        except Exception as e:
            logger.critical(f"Erro fatal: {str(e)}", exc_info=True)
            await self.tracker.update(zip_id, f"Erro geral ❌: {str(e)}", 1.0)
            return {"status": "error", "message": str(e)}
        
        return {"status": "success"}

    async def _process_zip_file(self, zip_path: Path, output_dir: Path, zip_id: str):
        await self.tracker.update(zip_id, "Iniciando extração", 0.1)
        extracted_files = await self.extractor.extract(zip_path, output_dir)
        
        await self.tracker.update(zip_id, "Buscando arquivo de chat", 0.15)
        chat_file = await self._find_chat_file(extracted_files, zip_id)
        
        await self.tracker.update(zip_id, "Processando chat", 0.20)
        chat_content = await read_file_async(chat_file)
        # Processo de audio
        chat_processor = ChatProcessor()
        audio_files = chat_processor.find_audio_files(chat_content)
        
       # 2. Cria o dicionário de áudios
        audio_dict = {
            file.name: file
            for file in extracted_files
            if file.suffix.lower() == '.opus'  # Ou outros formatos
        }
        
        # 3. Processa os áudios
        transcriptions = await self._process_audios(audio_dict, zip_id)
            
        # Atualiza o arquivo de chat (usando seu método existente)
        await chat_processor.update_chat_file(chat_file, transcriptions)
        # Fim audios

        await self._generate_report(chat_file, output_dir, zip_id)

    async def _find_chat_file(self, files: List[Path], zip_id: str) -> Path:
        chat_file = await asyncio.to_thread(
            self.chat_finder.find_chat_file, 
            files
        )
        if not chat_file:
            await self.tracker.update(zip_id, "Chat não encontrado", 0.3)
            raise ValueError("Arquivo de chat não encontrado")
        return chat_file

    async def _process_audios(
        self, 
        audio_dict: Dict[str, Path],  # Agora recebe o dicionário
        zip_id: str
    ) -> Dict[str, str]:
        """
        Processa os áudios e retorna dicionário {nome_arquivo: transcrição}
        
        Args:
            audio_dict: Dicionário {nome_arquivo: caminho_completo}
            zip_id: ID para acompanhamento do progresso
        """
        await self.tracker.update(zip_id, "Processando áudios", 0.3)
        
        # Prepara as tarefas de processamento
        tasks = []
        for i, (audio_name, audio_path) in enumerate(audio_dict.items()):
            # Atualiza progresso para cada arquivo
            progress = 0.3 + (i / len(audio_dict)) * 0.6
            tasks.append(
                self._process_single_audio(audio_name, audio_path, zip_id, progress)
            )
        
        # Executa em paralelo
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Constrói o dicionário final
        transcriptions = {}
        for audio_name, result in zip(audio_dict.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Erro ao processar {audio_name}: {str(result)}")
                transcriptions[audio_name] = f"[ERRO: {str(result)}]"
            else:
                transcriptions[audio_name] = result
        
        return transcriptions

    async def _process_single_audio(
        self,
        audio_name: str,
        audio_path: Path,
        zip_id: str,
        progress: float
    ) -> str:
        """Processa um único arquivo de áudio"""
        await self.tracker.update(
            zip_id,
            f"Transcrevendo {audio_name}",
            progress
        )
        
        try:
            return await self.transcriber.transcribe(audio_path)
        except Exception as e:
            logger.error(f"Falha na transcrição de {audio_name}", exc_info=True)
            raise e
        
        

    async def _generate_report(self, chat_file: Path, output_dir: Path, zip_id: str):
        await self.tracker.update(zip_id, "Gerando relatório", 0.6)
        
        # Garante que o diretório de saída existe
        output_dir.mkdir(parents=True, exist_ok=True)
        
        prompt_path = Path(__file__).parent.parent / "prompts" / "coach_prompt_corretor_imoveis.txt"
        filename = zip_id.replace(".zip", "")
        output_pdf = output_dir / f"analise_{filename}.pdf"
        
        try:
            await process_conversation_to_pdf(
                prompt_path,
                chat_file,
                output_pdf,
                self.tracker,
                zip_id
            )
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {str(e)}")
            raise

        await self.tracker.update(zip_id, "Excluindo conversa", 0.8)
        await self._cleanup_files()
        await self.tracker.update(zip_id, "Concluído", 1)

    async def _cleanup_files(self):
        await asyncio.to_thread(
            clean_extracted_files,
            base_dir=Path("storage"),
            keep_extensions=[".txt",".pdf"],
            delete_zips=True
        )

# Função assíncrona para leitura de arquivos
async def read_file_async(path: Path) -> str:
    """Leitura assíncrona com detecção de encoding"""
    async with aiofiles.open(path, 'rb') as f:
        content = await f.read()
        result = from_bytes(content).best()
        return str(result) if result else content.decode('utf-8', errors='replace')

# Ponto de entrada principal
async def process_zip(zip_path: Path) -> Dict[str, Optional[str]]:
    tracker = DatabaseStatusTracker()
    extractor = AsyncZipExtractor()
    chat_finder = create_chat_finder()
    
    if not (api_key := os.getenv("OPENAI_API_KEY")):
        raise RuntimeError("OPENAI_API_KEY não configurada")
    
    pipeline = ZipProcessingPipeline(
        extractor=extractor,
        chat_finder=chat_finder,
        transcriber=OpenAITranscriber(),
        status_tracker=tracker
    )
    
    return await pipeline.execute(zip_path)