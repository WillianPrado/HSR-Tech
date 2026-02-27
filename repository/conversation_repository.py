from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.conversation import Conversation
from schemas.conversation import ConversationSummary

logger = logging.getLogger(__name__)


def conversation_to_dict(conversation: Conversation) -> dict[str, Any]:
    """Serialize a Conversation entity to frontend-safe payload."""
    return {
        "id": str(conversation.id),
        "user_id": conversation.user_id,
        "title": conversation.title,
        "transcript": conversation.transcript,
        "analysis": conversation.analysis,
        "audio_path": conversation.audio_path,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


def get_conversation_by_id(db: Session, conversation_id: UUID) -> Conversation | None:
    """Return one conversation by primary key, or None when not found."""
    try:
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()
    except SQLAlchemyError:
        logger.exception("Database error while fetching conversation by id")
        raise


def get_conversation_by_id_for_frontend(
    db: Session,
    conversation_id: UUID,
) -> dict[str, Any] | None:
    """Return one conversation payload with string UUID for API/frontend usage."""
    conversation = get_conversation_by_id(db, conversation_id)
    if conversation is None:
        return None
    return conversation_to_dict(conversation)


def list_conversations_by_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[Conversation]:
    """List conversations for a user ordered by latest update."""
    safe_limit = max(1, min(limit, 200))
    safe_skip = max(0, skip)

    try:
        return (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(safe_skip)
            .limit(safe_limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error while listing conversations")
        raise


def list_conversations_by_user_for_frontend(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List conversation payloads with string UUID for API/frontend usage."""
    conversations = list_conversations_by_user(
        db=db,
        user_id=user_id,
        skip=skip,
        limit=limit,
    )
    return [conversation_to_dict(item) for item in conversations]


def list_conversation_summaries_by_user(
    db: Session,
    user_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[ConversationSummary]:
    """List lightweight conversation summaries selecting only required columns."""
    safe_limit = max(1, min(limit, 200))
    safe_skip = max(0, skip)

    try:
        rows = (
            db.query(
                Conversation.id,
                Conversation.title,
                Conversation.created_at,
                Conversation.updated_at,
            )
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(safe_skip)
            .limit(safe_limit)
            .all()
        )

        return [
            ConversationSummary(
                id=str(row.id),
                title=row.title,
                created_at=row.created_at.isoformat() if row.created_at else None,
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )
            for row in rows
        ]
    except SQLAlchemyError:
        logger.exception("Database error while listing conversation summaries")
        raise


def create_conversation(
    db: Session,
    *,
    user_id: int | None = None,
    title: str | None = None,
    transcript: str | None = None,
    audio_path: str | None = None,
    analysis: dict[str, Any] | None = None,
    conversation_id: UUID | None = None,
) -> Conversation:
    """Create and persist a conversation, auto-generating UUID when omitted."""
    new_conversation = Conversation(
        id=conversation_id or uuid4(),
        user_id=user_id,
        title=title,
        transcript=transcript,
        audio_path=audio_path,
        analysis=analysis,
    )

    try:
        db.add(new_conversation)
        db.commit()
        db.refresh(new_conversation)
        return new_conversation
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while creating conversation")
        raise


def update_conversation(
    db: Session,
    conversation_id: UUID,
    updates: dict[str, Any],
) -> Conversation | None:
    """Update allowed conversation fields and return updated entity."""
    allowed_fields = {"title", "transcript", "analysis", "audio_path"}
    payload = {key: value for key, value in updates.items() if key in allowed_fields}

    if not payload:
        return get_conversation_by_id(db, conversation_id)

    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if conversation is None:
            return None

        for key, value in payload.items():
            setattr(conversation, key, value)

        db.commit()
        db.refresh(conversation)
        return conversation
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while updating conversation")
        raise


def delete_conversation(db: Session, conversation_id: UUID) -> bool:
    """Delete conversation by id. Returns True if deleted, False if not found."""
    try:
        conversation = get_conversation_by_id(db, conversation_id)
        if conversation is None:
            return False

        db.delete(conversation)
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while deleting conversation")
        raise


def conversation_payload_for_ia(
    db: Session, conversation_id: UUID, not_system: bool = False
) -> dict[str, Any]:
    """
    Build a payload for IA API containing conversation details and all messages.
    If not_system is True, exclude messages with role 'system'.
    """
    from repository.message_repository import list_messages_by_conversation

    conversation = get_conversation_by_id(db, conversation_id)
    if not conversation:
        return {}
    messages = list_messages_by_conversation(db, conversation_id)
    if not_system:
        messages = [msg for msg in messages if msg.role != "system"]
    return {
        "id": str(conversation.id),
        "user_id": conversation.user_id,
        "title": conversation.title,
        "transcript": conversation.transcript,
        "analysis": conversation.analysis,
        "audio_path": conversation.audio_path,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
        "messages": [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    }
