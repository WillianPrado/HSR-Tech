import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from models.user import User
from schemas.analysis import AnalysisRequest, ContinueConversationRequest
from core.dependencies import (
    get_current_active_user,
    get_current_paid_user,
    get_db,
)
from services.analysis.analysis_use_cases import AnalysisUseCases

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Analysis"])


@router.post("/analysis/stream")
async def stream_message_analysis(
    request: AnalysisRequest,
    current_user: User = Depends(get_current_paid_user),
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
        use_cases = AnalysisUseCases(db)
        conversation_uuid, prompt_file = use_cases.validate_analysis_request(
            request.conversation_id,
            request.prompt_path,
            current_user,
        )

        return StreamingResponse(
            use_cases.analysis_stream_and_save(conversation_uuid, prompt_file, current_user),
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
        return AnalysisUseCases(db).list_conversation_messages(
            conversation_id=conversation_id,
            skip=skip,
            limit=limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_conversation_messages: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.post("/conversations/continue")
async def continue_conversation(
    request: ContinueConversationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Continue an existing conversation by adding a new user message and optional transcript/audio.
    Streams the AI response letter-by-letter for real-time frontend updates.
    """
    try:
        use_cases = AnalysisUseCases(db)
        return StreamingResponse(
            use_cases.continue_conversation(
                conversation_id=request.conversation_id,
                prompt=request.prompt,
                current_user=current_user,
            ),
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