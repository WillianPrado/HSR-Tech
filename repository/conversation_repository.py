from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.conversation import Conversation

logger = logging.getLogger(__name__)


def get_conversation_by_id(db: Session, conversation_id: UUID) -> Conversation | None:
    """Return one conversation by primary key, or None when not found."""
    try:
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()
    except SQLAlchemyError:
        logger.exception("Database error while fetching conversation by id")
        raise


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
