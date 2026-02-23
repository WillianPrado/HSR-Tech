from __future__ import annotations

from pydantic import BaseModel


class ConversationSummary(BaseModel):
    id: str
    title: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ConversationSummaryListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    conversations: list[ConversationSummary]