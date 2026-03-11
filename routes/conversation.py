import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from models.user import User
from repository.conversation_repository import list_conversation_summaries_by_user
from schemas.conversation import ConversationSummaryListResponse
from services.db_handler import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Conversations"])


@router.get("/conversations", response_model=ConversationSummaryListResponse)
async def list_user_conversations(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationSummaryListResponse:
    """List all conversations for the authenticated user."""
    try:
        conversations = list_conversation_summaries_by_user(
            db=db,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )

        return ConversationSummaryListResponse(
            total=len(conversations),
            skip=skip,
            limit=limit,
            conversations=conversations,
        )
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
