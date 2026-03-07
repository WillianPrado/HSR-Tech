import logging
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path

from fastapi.responses import FileResponse
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
    Retorna o PDF de análise gerado para o ZIP enviado.
    """
    _ = current_user
    filename = conversation_id.replace(".zip", "")
    
    output_pdf = Path(f"storage/output/analise_{filename}.pdf") 
    if not output_pdf.exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    return FileResponse(
        output_pdf,
        media_type="application/pdf",
        filename=output_pdf.name
    )

