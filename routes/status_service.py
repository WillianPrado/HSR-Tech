from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user
from models.status_response import StatusError, StatusProcessor, StatusResponse
from models.user import User

router = APIRouter(tags=["Status"])

@router.get("/status/{conversation_id}", response_model=StatusResponse)
async def check_conversation_status(
    conversation_id: str
    #,current_user: User = Depends(get_current_user)
):
    """
    Consulta assíncrona do status com timeout controlado
    
    Responses:
        200: Status do processamento
        404: Status não encontrado
        408: Timeout na consulta
        500: Erro interno no servidor
    """
    processor = StatusProcessor(conversation_id)
    response = await processor.get_status_response()
    
    if isinstance(response, StatusError):
        raise HTTPException(
            status_code=response.error_code,
            detail=response.detail
        )
    
    return response