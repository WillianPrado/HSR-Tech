from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncGenerator
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.dependencies import consume_analysis_credit, enforce_analysis_access
from models.user import User
from repository.conversation_repository import (
    conversation_payload_for_ia,
    get_conversation_by_id,
    update_conversation,
)
from repository.message_repository import create_message, list_messages_by_conversation
from services.chat.conversation_title_service import (
    should_update_conversation_title,
    suggest_conversation_title,
)
from services.reports.coach_analyzer import send_analysis_prompt
from services.reports.llm_factory import get_llm_client

logger = logging.getLogger(__name__)

CONTINUE_CONVERSATION_SYSTEM_INSTRUCTION = (
    "Voce e um analista comercial especializado em consorcio. "
    "Responda sempre em Markdown valido e estruturado, sem bloco de codigo. "
    "Use este formato minimo: "
    "# Titulo; secoes com subtitulos em negrito (**secao**); listas com '-' quando aplicavel. "
    "Se citar datas, use ISO-8601 quando possivel."
)


class AnalysisUseCases:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid conversation_id format. Must be a valid UUID.",
            ) from exc

    def _get_conversation_or_404(self, conversation_id: UUID):
        conversation = get_conversation_by_id(self.db, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"Conversation not found: {conversation_id}")
        return conversation

    def validate_analysis_request(self, conversation_id: str, prompt_path: str, current_user: User) -> tuple[UUID, Path]:
        conversation_uuid = self._to_uuid(conversation_id)
        _ = self._get_conversation_or_404(conversation_uuid)

        prompt_file = Path(prompt_path)
        if not prompt_file.exists():
            raise HTTPException(status_code=404, detail=f"Prompt file not found: {prompt_path}")

        _ = enforce_analysis_access(current_user)
        return conversation_uuid, prompt_file

    async def analysis_stream_and_save(
        self,
        conversation_id: UUID,
        prompt_path: Path,
        current_user: User,
    ) -> AsyncGenerator[str, None]:
        try:
            ai_response = ""
            received_any_chunk = False

            async for chunk in send_analysis_prompt(self.db, conversation_id, prompt_path):
                received_any_chunk = True
                ai_response += chunk
                for char in chunk:
                    yield char
                    await asyncio.sleep(0.01)

            if not received_any_chunk:
                raise RuntimeError("Empty AI streaming response")

            conversation = get_conversation_by_id(self.db, conversation_id)
            if conversation and should_update_conversation_title(conversation.title):
                title_mode = os.getenv("TITLE_GENERATION_MODE", "hybrid").strip().lower()
                title_client = get_llm_client("deepseek") if title_mode in {"hybrid", "llm"} else None
                source_text = ai_response.strip()
                if source_text:
                    title = await suggest_conversation_title(source_text[:2000], llm_client=title_client)
                    if title:
                        update_conversation(self.db, conversation_id, {"title": title})

            create_message(
                self.db,
                conversation_id=conversation_id,
                role="assistant",
                content=ai_response,
            )
            consume_analysis_credit(self.db, current_user.id)

        except RuntimeError as exc:
            logger.error(f"Streaming analysis runtime error: {exc}")
            yield f"\n\n[ERRO] {str(exc)}"
        except Exception:
            logger.exception("Streaming analysis error")
            yield "\n\n[ERRO] Unexpected error during analysis"

    def list_conversation_messages(self, conversation_id: str, skip: int, limit: int) -> dict:
        conversation_uuid = self._to_uuid(conversation_id)
        conversation = self._get_conversation_or_404(conversation_uuid)

        messages = [
            msg
            for msg in list_messages_by_conversation(self.db, conversation_uuid, skip=skip, limit=limit)
            if msg.role != "system"
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
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ],
        }

    async def continue_conversation(self, conversation_id: str, prompt: str, current_user: User) -> AsyncGenerator[str, None]:
        _ = enforce_analysis_access(current_user)

        conversation_uuid = self._to_uuid(conversation_id)
        conversation = self._get_conversation_or_404(conversation_uuid)

        create_message(
            self.db,
            conversation_id=conversation.id,
            role="user",
            content=prompt,
        )

        conversation_payload = conversation_payload_for_ia(self.db, conversation.id, not_system=True)
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation_payload.get("messages", [])
        ]
        messages = [
            {"role": "system", "content": CONTINUE_CONVERSATION_SYSTEM_INSTRUCTION},
            *messages,
        ]

        llm_client = get_llm_client("openai")
        ai_response = ""
        async for chunk in llm_client.stream_messages(messages):
            ai_response += chunk
            for char in chunk:
                yield char
                await asyncio.sleep(0.01)

        create_message(
            self.db,
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response,
        )
        consume_analysis_credit(self.db, current_user.id)
