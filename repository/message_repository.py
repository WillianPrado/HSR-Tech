from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from models.message import Message

logger = logging.getLogger(__name__)


def get_message_by_id(db: Session, message_id: UUID) -> Message | None:
    """Return one message by primary key, or None when not found."""
    try:
        return db.query(Message).filter(Message.id == message_id).first()
    except SQLAlchemyError:
        logger.exception("Database error while fetching message by id")
        raise


def list_messages_by_conversation(
    db: Session,
    conversation_id: UUID,
    skip: int = 0,
    limit: int = 200,
) -> list[Message]:
    """List messages for a conversation ordered by creation time."""
    safe_limit = max(1, min(limit, 500))
    safe_skip = max(0, skip)

    try:
        return (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(safe_skip)
            .limit(safe_limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error while listing messages")
        raise


def create_message(
    db: Session,
    *,
    conversation_id: UUID,
    role: str,
    content: str,
    message_id: UUID | None = None,
) -> Message:
    """Create and persist a message, auto-generating UUID when omitted."""
    db_message = Message(
        id=message_id or uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
    )

    try:
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while creating message")
        raise


def update_message_content(
    db: Session,
    message_id: UUID,
    content: str,
) -> Message | None:
    """Update message content and return updated entity."""
    try:
        db_message = get_message_by_id(db, message_id)
        if db_message is None:
            return None

        db_message.content = content
        db.commit()
        db.refresh(db_message)
        return db_message
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while updating message")
        raise


def delete_message(db: Session, message_id: UUID) -> bool:
    """Delete message by id. Returns True if deleted, False if not found."""
    try:
        db_message = get_message_by_id(db, message_id)
        if db_message is None:
            return False

        db.delete(db_message)
        db.commit()
        return True
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while deleting message")
        raise
