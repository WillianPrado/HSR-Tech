import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from uuid import UUID
from pathlib import Path
from sqlalchemy.orm import Session
import json
from pydantic import BaseModel

from services.reports.coach_analyzer import send_analysis_prompt
from repository.message_repository import create_message
from repository.conversation_repository import get_conversation_by_id
from core.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analysis"])


class AnalysisRequest(BaseModel):
    """Request body for streaming analysis."""
    conversation_id: str
    prompt_path: str


async def event_generator(db: Session, conversation_id: UUID, prompt_path: Path):
    """Generate SSE events from streaming analysis and save result as message."""
    try:
        # Collect all chunks while streaming
        full_response = []
        async for chunk in send_analysis_prompt(db, conversation_id, prompt_path):
            full_response.append(chunk)
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        # Concatenate all chunks
        response_text = "".join(full_response)
        
        if not response_text:
            raise RuntimeError("Empty AI response")
        
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
            "message_length": len(response_text)
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
        
        # Get all messages
        messages = list_messages_by_conversation(
            db,
            conversation_uuid,
            skip=skip,
            limit=limit
        )
        
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
