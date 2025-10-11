import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional
from anyio import Path
from datetime import datetime

from services.reports.deepseek_client import enviar_mensagem_para_deepseek
from services.reports.pdf_utils import salvar_markdown_em_pdf_visual
from core.status_tracker import set_status

logger = logging.getLogger(__name__)


# ======================================================================
# Abstract Interface for Tracking Progress
# ======================================================================

class StatusTracker(ABC):
    """Abstract interface for tracking process status."""
    
    @abstractmethod
    async def update(self, zip_id: str, message: str, progress: float):
        """Update the process status."""
        pass


class DatabaseStatusTracker(StatusTracker):
    """Tracks process status in the database."""
    
    async def update(self, zip_id: str, message: str, progress: float):
        await set_status(zip_id, message, progress)


# ======================================================================
# File Utilities
# ======================================================================

def load_file_sync(path: Path) -> Optional[str]:
    """Synchronously reads a file (wrapped later in asyncio.to_thread)."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"❌ Error reading file '{path}': {e}")
        return None


def combine_prompt_and_chat(prompt: str, conversation: str) -> str:
    """Combines the base prompt with the conversation content."""
    return f"{prompt}\n\nCONVERSATION TRANSCRIPT:\n{conversation}"


# ======================================================================
# Main Asynchronous Processing Function
# ======================================================================

async def process_conversation_to_pdf(
    prompt_path: Path,
    chat_path: Path,
    output_pdf: Path,
    tracker: Optional[StatusTracker] = None,
    zip_id: Optional[str] = None
):
    """
    Process a conversation and generate an analytical PDF report.
    Handles file loading, AI analysis, and PDF creation asynchronously.

    Args:
        prompt_path: Path to the prompt text file.
        chat_path: Path to the conversation text file.
        output_pdf: Output path for the generated PDF.
        tracker: Optional status tracker instance.
        zip_id: Optional ID for process tracking.
    """

    async def update_status(message: str, progress: float):
        """Update progress safely if tracker is available."""
        if tracker and zip_id:
            await tracker.update(zip_id, message, progress)

    def validate_file(path: Path, description: str) -> Optional[str]:
        """Validate that the given file path exists."""
        if not path.exists():
            return f"{description} not found: {path}"
        return None

    try:
        # ------------------------------------------------------------------
        # 1️⃣ Validate Input Files
        # ------------------------------------------------------------------
        for desc, path in [("Prompt file", prompt_path), ("Chat file", chat_path)]:
            if (error := validate_file(path, desc)):
                await update_status(error, 0)
                raise FileNotFoundError(error)

        # ------------------------------------------------------------------
        # 2️⃣ Load Files (non-blocking using asyncio.to_thread)
        # ------------------------------------------------------------------
        await update_status("Loading files...", 0.2)
        prompt, conversation = await asyncio.gather(
            asyncio.to_thread(load_file_sync, prompt_path),
            asyncio.to_thread(load_file_sync, chat_path)
        )

        if not prompt or not conversation:
            msg = "Invalid prompt or conversation content."
            await update_status(msg, 0)
            raise ValueError(msg)

        # ------------------------------------------------------------------
        # 3️⃣ Prepare Analysis
        # ------------------------------------------------------------------
        await update_status("Preparing analysis...", 0.4)
        full_message = combine_prompt_and_chat(prompt, conversation)

        # ------------------------------------------------------------------
        # 4️⃣ AI Analysis (synchronous call wrapped in thread)
        # ------------------------------------------------------------------
        await update_status("AI analyzing negotiation... (may take a few minutes)", 0.65)
        ai_response = await asyncio.to_thread(enviar_mensagem_para_deepseek, full_message)

        if not ai_response:
            msg = "Empty AI response."
            await update_status(msg, 0)
            raise RuntimeError(msg)

        # ------------------------------------------------------------------
        # 5️⃣ Generate PDF
        # ------------------------------------------------------------------
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        await update_status("Generating PDF report...", 0.8)
        await asyncio.to_thread(salvar_markdown_em_pdf_visual, ai_response, output_pdf)

        logger.info(f"✅ PDF report successfully generated: {output_pdf}")
        await update_status("Report generation completed.", 1.0)

    except (FileNotFoundError, ValueError, RuntimeError) as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        await update_status(error_msg, 0)
        logger.error(error_msg)
        raise

    except Exception as e:
        error_msg = f"Unexpected error during processing: {str(e)}"
        await update_status(error_msg, 0)
        logger.exception(error_msg)
        raise
