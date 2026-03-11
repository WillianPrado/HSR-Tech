import logging
from fastapi import APIRouter, Depends, HTTPException
from core.dependencies import get_current_paid_user
from models.user import User


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Report"])

@router.get("/results/{conversation_id}/report")
async def get_pdf_report(
    conversation_id: str,
    current_user: User = Depends(get_current_paid_user),
):
    """
    Endpoint descontinuado: o PDF agora e gerado no frontend.
    """
    _ = (current_user, conversation_id)
    raise HTTPException(
        status_code=410,
        detail="Geracao e download de PDF foram removidos do backend. O frontend deve renderizar o relatorio.",
    )

