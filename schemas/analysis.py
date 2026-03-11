from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    """Request body for streaming analysis."""

    conversation_id: str
    prompt_path: str


class ContinueConversationRequest(BaseModel):
    conversation_id: str
    prompt: str
    transcript: str | None = None
    audio_path: str | None = None
