import logging
from fastapi import APIRouter, HTTPException
from pathlib import Path

from fastapi.responses import FileResponse


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Report"])

@router.get("/results/{zip_id}/report")
async def get_pdf_report(zip_id: str):
    """
    Retorna o PDF de análise gerado para o ZIP enviado.
    """
    # Remove a extensão .zip, se houver
    filename = zip_id.replace(".zip", "")
    
    output_pdf = Path(f"storage/output/analise_{filename}.pdf") 
    if not output_pdf.exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    return FileResponse(
        output_pdf,
        media_type="application/pdf",
        filename=output_pdf.name
    )

