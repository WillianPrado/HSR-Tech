# core/tasks.py
"""
Module: core.tasks
Author: Willian Prado
Description:
    Main asynchronous pipeline responsible for processing uploaded ZIP files
    that contain chat exports and audio attachments. Implements a clean, SOLID,
    non-blocking workflow with structured logging and progress tracking.

Architecture:
    - Strategy interfaces for tracking and transcription
    - Pipeline orchestrator coordinating ZIP extraction, chat parsing, audio
      transcription, and report generation
    - Asynchronous I/O using aiofiles and asyncio.gather
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID
from abc import ABC, abstractmethod

import aiofiles
from charset_normalizer import from_bytes
from mysqlx import Session

from repository.conversation_repository import create_conversation, update_conversation
from services.zip.zip_extractor import AsyncZipExtractor
from services.chat.chat_file_handler import ChatProcessor
from services.audio.openai_transcriber import OpenAITranscriber
from services.reports.coach_analyzer import create_analysis_prompt, process_conversation_to_pdf
from core.config import settings
from utils.find_chat_file import create_chat_finder, ChatFileFinder
from utils.file_cleaner import clean_extracted_files
from core.status_tracker import set_status

logger = logging.getLogger(__name__)


# =====================================================================
# STATUS TRACKING
# =====================================================================

class StatusTracker(ABC):
    """Abstract interface for progress tracking and status updates."""

    @abstractmethod
    async def update(self, conversation_id: str, message: str, progress: float):
        """Persist the current processing status."""
        raise NotImplementedError


class DatabaseStatusTracker(StatusTracker):
    """Concrete tracker that persists progress to the database."""

    async def update(self, conversation_id: str, message: str, progress: float):
        await set_status(conversation_id, message, progress)


# =====================================================================
# AUDIO PROCESSING
# =====================================================================

class AudioProcessor:
    """Handles transcription of individual audio files."""

    def __init__(self, transcriber: OpenAITranscriber):
        self.transcriber = transcriber

    async def process_audio(self, audio_path: Path) -> str:
        """
        Transcribes a single audio file asynchronously using OpenAITranscriber.
        The heavy work is delegated to a thread pool to avoid blocking.
        """
        return await self.transcriber.transcribe(str(audio_path))


# =====================================================================
# ZIP PIPELINE ORCHESTRATOR
# =====================================================================

class ZipProcessingPipeline:
    """
    Coordinates the full ZIP file workflow:
        1. Extraction
        2. Chat detection and parsing
        3. Audio transcription
        4. PDF report generation
        5. Cleanup
    """

    def __init__(
        self,
        extractor: AsyncZipExtractor,
        chat_finder: ChatFileFinder,
        transcriber: OpenAITranscriber,
        status_tracker: StatusTracker,
    ):
        self.extractor = extractor
        self.chat_finder = chat_finder
        self.transcriber = transcriber
        self.tracker = status_tracker
        self.max_concurrent_transcriptions = max(1, settings.MAX_CONCURRENT_TRANSCRIPTIONS)

    # -----------------------------------------------------------------
    async def execute(self, zip_path: Path, user_id: int, db: Session, conversation_id: str) -> Dict[str, Optional[str]]:
        """Entry point: orchestrates full processing of a ZIP file."""
        base_dir = Path("storage")
        output_dir = base_dir / "output"

        try:
            await self._process_zip_file(zip_path, output_dir, conversation_id, user_id, db)
        except Exception as e:
            logger.critical(f"Fatal error: {e}", exc_info=True)
            await self.tracker.update(conversation_id, f"Erro geral ❌: {e}", 1.0)
            return {"status": "error", "message": str(e)}

        return {"status": "success"}

    # -----------------------------------------------------------------
    async def _process_zip_file(self, 
                                zip_path: Path, 
                                output_dir: Path, 
                                conversation_id: str,
                                user_id: int,
                                db: Session):
        """Main execution chain for a single ZIP package."""
        await self.tracker.update(conversation_id, "Iniciando extração", 0.1)
        extracted_files = await self.extractor.extract(zip_path, output_dir)

        chat_file = await self._find_chat_file(extracted_files, conversation_id)

        await self.tracker.update(conversation_id, "Processando chat", 0.20)
        chat_content = await read_file_async(chat_file)

        chat_processor = ChatProcessor()
        _ = chat_processor.find_audio_files(chat_content)  # Reserved for parsing consistency

        # Collect audio files inside extracted content
        audio_dict = {
            file.name: file
            for file in extracted_files
            if file.suffix.lower() in (".opus", ".m4a", ".mp3")
        }

        transcriptions = await self._process_audios(audio_dict, conversation_id)
        await chat_processor.update_chat_file(chat_file, transcriptions)
        conversation = await read_file_async(chat_file)
       # await self._generate_report(chat_file, output_dir, conversation_id)

        conversation_uuid = UUID(conversation_id)
        updated = update_conversation(
            db=db,
            conversation_id=conversation_uuid,
            updates={
                "transcript": conversation
            },
        )

        if updated is None:
            create_conversation(
                db=db,
                user_id=user_id,
                conversation_id=conversation_uuid,
                title=f"Análise {zip_path.stem}",
                transcript=conversation,
                audio_path=str(chat_file),
            )
        
        await self.tracker.update(conversation_id, "Conversa salva no banco de dados", 0.85)

    # -----------------------------------------------------------------
    async def _find_chat_file(self, files: List[Path], conversation_id: str) -> Path:
        """
        Fully asynchronous chat file detection using ChatFileFinder.
        Updates status while scanning to keep UI responsive.
        """
        await self.tracker.update(conversation_id, "Buscando arquivo de chat", 0.15)

        try:
            chat_file = await asyncio.wait_for(
                self.chat_finder.find_chat_file_async(files),
                timeout=30
            )
        except asyncio.TimeoutError:
            await self.tracker.update(conversation_id, "Busca de chat expirou (timeout)", 0.3)
            raise TimeoutError("Chat search timed out")
        except Exception as e:
            await self.tracker.update(conversation_id, f"Erro ao buscar chat: {e}", 0.3)
            raise

        if not chat_file:
            await self.tracker.update(conversation_id, "Chat não encontrado", 0.3)
            raise FileNotFoundError("Nenhum arquivo de chat válido foi encontrado")

        await self.tracker.update(conversation_id, f"Chat encontrado: {chat_file.name}", 0.18)
        return chat_file

    # -----------------------------------------------------------------
    async def _process_audios(self, audio_dict: Dict[str, Path], conversation_id: str) -> Dict[str, str]:
        """Runs concurrent transcription of all audio files."""
        await self.tracker.update(conversation_id, "Processando áudios", 0.3)

        if not audio_dict:
            logger.info("No audio files detected in ZIP.")
            return {}

        semaphore = asyncio.Semaphore(self.max_concurrent_transcriptions)
        tasks = []
        for i, (audio_name, audio_path) in enumerate(audio_dict.items()):
            progress = 0.3 + (i / max(len(audio_dict), 1)) * 0.6
            tasks.append(
                self._process_single_audio(
                    audio_name,
                    audio_path,
                    conversation_id,
                    progress,
                    semaphore,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        transcriptions: Dict[str, str] = {}
        for audio_name, result in zip(audio_dict.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Error processing {audio_name}: {result}")
                transcriptions[audio_name] = f"[ERRO: {result}]"
            else:
                transcriptions[audio_name] = result

        return transcriptions

    # -----------------------------------------------------------------
    async def _process_single_audio(
        self,
        audio_name: str,
        audio_path: Path,
        conversation_id: str,
        progress: float,
        semaphore: asyncio.Semaphore,
    ) -> str:
        """Transcribes a single audio file with progress feedback."""
        await self.tracker.update(conversation_id, f"Transcrevendo {audio_name}", progress)

        try:
            async with semaphore:
                return await self.transcriber.transcribe(audio_path)
        except Exception as e:
            logger.error(f"Falha na transcrição de {audio_name}", exc_info=True)
            raise

    # -----------------------------------------------------------------
    async def _generate_report(self, chat_file: Path, output_dir: Path, zip_id: str):
        """Generates a PDF report using the processed chat file."""
        await self.tracker.update(zip_id, "Gerando relatório", 0.6)
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt_path = (
            Path(__file__).parent.parent / "prompts" / "coach_prompt_corretor_imoveis.txt"
        )
        filename = zip_id.replace(".zip", "")
        output_pdf = output_dir / f"analise_{filename}.pdf"

        

        await self.tracker.update(zip_id, "Excluindo conversa", 0.8)
        await self._cleanup_files()
        create_conversation(
            user_id=1,  # Placeholder: replace with actual user ID from context
            title=f"Análise {filename}",
            audio_path=str(chat_file),
        )

    # -----------------------------------------------------------------
    async def _cleanup_files(self):
        """Deletes temporary extracted files while preserving reports."""
        await asyncio.to_thread(
            clean_extracted_files,
            base_dir=Path("storage"),
            keep_extensions=[".txt", ".pdf"],
            delete_zips=True,
        )


# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

async def read_file_async(path: Path) -> str:
    """
    Asynchronously reads a text file and auto-detects encoding.
    Fallbacks to UTF-8 with replacement for unknown chars.
    """
    async with aiofiles.open(path, "rb") as f:
        content = await f.read()
        result = from_bytes(content).best()
        return str(result) if result else content.decode("utf-8", errors="replace")


# =====================================================================
# ENTRY POINT
# =====================================================================

async def process_zip(
    zip_path: Path,
    user_id: Optional[int] = None,
    db: Optional[Session] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Main entry point used by FastAPI route or background worker."""
    zip_path = Path(zip_path)
    conversation_id = conversation_id or zip_path.stem

    if user_id is None or db is None:
        await set_status(conversation_id, "Configuração incompleta para processar o ZIP", 1.0)
        return {
            "status": "error",
            "message": "user_id e db são obrigatórios para salvar conversa",
        }

    if not (api_key := os.getenv("OPENAI_API_KEY")):
        raise RuntimeError("OPENAI_API_KEY not configured")

    tracker = DatabaseStatusTracker()
    extractor = AsyncZipExtractor()
    chat_finder = create_chat_finder()
    transcriber = OpenAITranscriber()

    pipeline = ZipProcessingPipeline(
        extractor=extractor,
        chat_finder=chat_finder,
        transcriber=transcriber,
        status_tracker=tracker,
    )

    return await pipeline.execute(zip_path, user_id, db, conversation_id)
