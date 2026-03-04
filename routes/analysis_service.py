import asyncio
import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from uuid import UUID
from pathlib import Path
from sqlalchemy.orm import Session
from pydantic import BaseModel
from services.reports.llm_factory import get_llm_client
from services.chat.conversation_title_service import (
    should_update_conversation_title,
    suggest_conversation_title,
)

from services.reports.coach_analyzer import send_analysis_prompt
from repository.message_repository import create_message
from repository.conversation_repository import (
    conversation_payload_for_ia,
    get_conversation_by_id,
    create_conversation,
    update_conversation,
)
from core.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analysis"])

CONTINUE_CONVERSATION_SYSTEM_INSTRUCTION = (
    "Você é um analista comercial especializado em consórcio. "
    "Responda sempre em Markdown válido e estruturado, sem bloco de código. "
    "Use este formato mínimo: "
    "# Título; seções com subtítulos em negrito (**secao**); listas com '-' quando aplicável. "
    "Se citar datas, use ISO-8601 quando possível."
)


class AnalysisRequest(BaseModel):
    """Request body for streaming analysis."""
    conversation_id: str
    prompt_path: str


class StartConversationRequest(BaseModel):
    user_id: int
    initial_prompt: str
    transcript: str | None = None
    audio_path: str | None = None


class ContinueConversationRequest(BaseModel):
    conversation_id: str
    prompt: str
    transcript: str | None = None
    audio_path: str | None = None


async def analysis_stream_and_save(db: Session, conversation_id: UUID, prompt_path: Path):
    """Stream analysis text progressively and save final assistant message."""
    try:
        ai_response = ""
        received_any_chunk = False

        async for chunk in send_analysis_prompt(db, conversation_id, prompt_path):
            received_any_chunk = True
            ai_response += chunk
            for char in chunk:
                yield char
                await asyncio.sleep(0.01)

        if not received_any_chunk:
            raise RuntimeError("Empty AI streaming response")

        conversation = get_conversation_by_id(db, conversation_id)
        if conversation and should_update_conversation_title(conversation.title):
            title_mode = os.getenv("TITLE_GENERATION_MODE", "hybrid").strip().lower()
            title_client = get_llm_client("deepseek") if title_mode in {"hybrid", "llm"} else None
            source_text = ai_response.strip()
            if source_text:
                title = await suggest_conversation_title(source_text[:2000], llm_client=title_client)
                if title:
                    update_conversation(db, conversation_id, {"title": title})
        
        # Save the complete response as a message in the conversation
        create_message(
            db,
            conversation_id=conversation_id,
            role="assistant",
            content=ai_response
        )
        
    except RuntimeError as e:
        logger.error(f"Streaming analysis runtime error: {e}")
        yield f"\n\n[ERRO] {str(e)}"
    except Exception as e:
        logger.exception(f"Streaming analysis error: {e}")
        yield "\n\n[ERRO] Unexpected error during analysis"


@router.post("/analysis/stream")
async def stream_message_analysis(
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Stream AI analysis for a conversation and save the final response.
    
    Args:
        request: AnalysisRequest with conversation_id and prompt_path
        
    Returns:
        StreamingResponse with incremental text chunks.
        
    Raises:
        HTTPException: 400 if conversation_id is not a valid UUID
        HTTPException: 404 if conversation or prompt file not found
    """
    try:
        # Validate conversation_id is a valid UUID
        try:
            conversation_uuid = UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id format. Must be a valid UUID.")
        
        # Validate conversation exists
        conversation = get_conversation_by_id(db, conversation_uuid)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation not found: {request.conversation_id}")
        
        # Validate prompt_path exists
        prompt_file = Path(request.prompt_path)
        if not prompt_file.exists():
            raise HTTPException(status_code=404, detail=f"Prompt file not found: {request.prompt_path}")
        
        return StreamingResponse(
            analysis_stream_and_save(db, conversation_uuid, prompt_file),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in stream_message_analysis: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """
    Retrieve all messages in a conversation.
    
    Args:
        conversation_id: UUID of the conversation
        skip: Number of messages to skip (pagination offset)
        limit: Maximum number of messages to return (1-500, default 200)
        
    Returns:
        Dictionary with messages list and metadata
        
    Raises:
        HTTPException: 400 if conversation_id is not a valid UUID
        HTTPException: 404 if conversation not found
    """
    try:
        # Validate conversation_id is a valid UUID
        try:
            conversation_uuid = UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id format. Must be a valid UUID.")
        
        # Validate conversation exists
        conversation = get_conversation_by_id(db, conversation_uuid)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
        
        # Import here to avoid circular imports
        from repository.message_repository import list_messages_by_conversation
        
        # Get all messages, excluding 'system' role
        messages = [
            msg for msg in list_messages_by_conversation(
                db,
                conversation_uuid,
                skip=skip,
                limit=limit
            ) if msg.role != "system"
        ]
        return {
            "conversation_id": str(conversation_uuid),
            "conversation_title": conversation.title,
            "total_messages": len(messages),
            "skip": skip,
            "limit": limit,
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_conversation_messages: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



def load_file_sync(path: Path) -> Optional[str]:
    """Synchronously reads a file (wrapped later in asyncio.to_thread)."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"❌ Error reading file '{path}': {e}")
        return None 
    
@router.post("/conversations/continue")
async def continue_conversation(
    request: ContinueConversationRequest,
    db: Session = Depends(get_db)
):
    """
    Continue an existing conversation by adding a new user message and optional transcript/audio.
    Streams the AI response letter-by-letter for real-time frontend updates.
    """
    try:
        # Validate conversation_id
        try:
            conversation_uuid = UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation_id format. Must be a valid UUID.")

        conversation = get_conversation_by_id(db, conversation_uuid)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation not found: {request.conversation_id}")
        # Add new user message
        create_message(
            db,
            conversation_id=conversation.id,
            role="user",
            content=request.prompt
        )        # Get messages excluding 'system' role
        conversation_payload = conversation_payload_for_ia(db, conversation.id, not_system=True)
        messages = [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in conversation_payload.get("messages", [])
        ]

        messages = [
            {
                "role": "system",
                "content": CONTINUE_CONVERSATION_SYSTEM_INSTRUCTION,
            },
            *messages,
        ]

        llm_client = get_llm_client('openai')

        async def ai_stream_and_save():
            ai_response = ""
            async for chunk in llm_client.stream_messages(messages):
                ai_response += chunk
                for char in chunk:
                    yield char
                    await asyncio.sleep(0.01)  # Force flush for each char
            create_message(
                db,
                conversation_id=conversation.id,
                role="assistant",
                content=ai_response
            )

        return StreamingResponse(
            ai_stream_and_save(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error continuing conversation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")