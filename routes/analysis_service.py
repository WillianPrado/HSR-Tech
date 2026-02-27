import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from uuid import UUID
from pathlib import Path
from sqlalchemy.orm import Session
import json
from pydantic import BaseModel
from services.reports.deepseek_client import DeepSeekClient

from services.reports.coach_analyzer import send_analysis_prompt
from repository.message_repository import create_message
from repository.conversation_repository import conversation_payload_for_ia, get_conversation_by_id, create_conversation
from core.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analysis"])


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


def _extract_json_objects(buffer: str) -> tuple[list[dict], str]:
    """Extract complete top-level JSON objects from a text buffer."""
    objects: list[dict] = []
    depth = 0
    start_idx = -1
    in_string = False
    escape = False

    for index, char in enumerate(buffer):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            if depth == 0:
                start_idx = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx != -1:
                    candidate = buffer[start_idx:index + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            objects.append(parsed)
                    except json.JSONDecodeError:
                        pass
                    start_idx = -1

    remainder = ""
    if depth > 0 and start_idx != -1:
        remainder = buffer[start_idx:]

    return objects, remainder


async def event_generator(db: Session, conversation_id: UUID, prompt_path: Path):
    """Generate SSE events from structured JSON sections and save final result as message."""
    try:
        chunk_buffer = ""
        section_payloads: list[dict] = []

        async for chunk in send_analysis_prompt(db, conversation_id, prompt_path):
            chunk_buffer += chunk

            parsed_objects, chunk_buffer = _extract_json_objects(chunk_buffer)

            for section_obj in parsed_objects:
                section_name = section_obj.get("section")
                if section_name == "done":
                    continue

                if not all(key in section_obj for key in ("section", "title", "content")):
                    continue

                section_payloads.append(section_obj)
                yield f"event: section\ndata: {json.dumps(section_obj, ensure_ascii=False)}\n\n"

        if not section_payloads:
            raise RuntimeError("Empty or invalid structured AI response")

        response_text = "\n\n".join(
            f"## {item['title']}\n{item['content']}" for item in section_payloads
        )
        
        # Save the complete response as a message in the conversation
        saved_message = create_message(
            db,
            conversation_id=conversation_id,
            role="assistant",
            content=response_text
        )
        
        # Send completion event with saved message details
        completion_data = {
            "status": "completed",
            "message_id": str(saved_message.id),
            "message_length": len(response_text),
            "sections": [item["section"] for item in section_payloads],
        }
        yield f"event: done\ndata: {json.dumps(completion_data)}\n\n"
        
    except RuntimeError as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    except Exception as e:
        logger.exception(f"Streaming analysis error: {e}")
        yield f"event: error\ndata: {json.dumps({'error': 'Unexpected error during analysis'})}\n\n"


@router.post("/analysis/stream")
async def stream_message_analysis(
    request: AnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Stream AI analysis for a conversation and automatically save the response.
    
    The streamed response is collected and saved as an 'assistant' message 
    in the specified conversation after streaming completes.
    
    Args:
        request: AnalysisRequest with conversation_id and prompt_path
        
    Returns:
        Server-Sent Events stream with:
        - data events: Analysis chunks with JSON payload {"content": "..."}
        - done event: Completion summary with saved message ID
        - error event: Error details if analysis fails
        
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
            event_generator(db, conversation_uuid, prompt_file),
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
        )
        # Get messages excluding 'system' role
        conversation_payload = conversation_payload_for_ia(db, conversation.id, not_system=True)
        messages = [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in conversation_payload.get("messages", [])
        ]
        deepseek_client = DeepSeekClient()
        # Return streaming response to frontend and save AI response to DB
        async def ai_stream_and_save():
            ai_response = ""
            async for chunk in deepseek_client.stream_messages(messages):
                ai_response += chunk
                yield chunk
            # Save the complete AI response as a message
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
