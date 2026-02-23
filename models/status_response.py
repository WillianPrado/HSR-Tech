import asyncio
from datetime import datetime
import logging
from typing import List, Optional, Dict, Tuple, Union
from pydantic import BaseModel
from core.status_tracker import get_status
from models.user import User

logger = logging.getLogger(__name__)

## Modelos Pydantic (Contrato da API)
class HistoryItem(BaseModel):
    status: str
    timestamp: str
    progress: float

class StatusResults(BaseModel):
    transcriptions: Optional[str] = None
    pdf_report: Optional[str] = None
    analysis_data: Optional[str] = None

class StatusResponse(BaseModel):
    conversation_id: str
    status: str
    history: Optional[List[HistoryItem]] = None
    progress: float
    timestamp: str
    message: str
    results: Optional[StatusResults] = None

class StatusError(BaseModel):
    error_code: int
    detail: str

## Lógica de Processamento de Status (SRP)
class StatusProcessor:
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        #self.current_user = current_user
        self.timeout = 10.0  # Configurável

    async def get_status_response(self) -> Union[StatusResponse, StatusError]:
        """
        Obtém e formata o status do processamento
        
        Returns:
            Union[StatusResponse, StatusError]: Retorna o status ou um erro formatado
        """
        status_data = await self._fetch_status()
        if isinstance(status_data, StatusError):
            return status_data
            
        return self._build_response(status_data)

    async def _fetch_status(self) -> Union[Dict, StatusError]:
        """Busca o status com tratamento de timeout"""
        try:
            return await asyncio.wait_for(get_status(self.conversation_id), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ao buscar status para {self.conversation_id}")
            return StatusError(
                error_code=408,
                detail="Request timeout"
            )
        except Exception as e:
            logger.error(f"Erro ao buscar status: {str(e)}")
            return StatusError(
                error_code=500,
                detail="Erro interno ao verificar status"
            )

    def _build_response(self, status_data: Dict) -> Union[StatusResponse, StatusError]:
        """Constrói a resposta padronizada"""
        if not status_data or "current" not in status_data:
            logger.warning(f"Status não encontrado para {self.conversation_id}")
            return StatusError(
                error_code=404,
                detail="Status não encontrado ou não atualizado ainda"
            )

        base_response = {
            "conversation_id": self.conversation_id,
            "status": status_data.get("current", {}).get("status", "unknown"),
            "history": status_data.get("history", []),
            "progress": status_data.get("current", {}).get("progress", 0),
            "timestamp": datetime.now().isoformat(),
            "message": self._get_status_message(status_data)
        }

        if "Concluído" in base_response["status"]:
            base_response["results"] = self._build_results()

        return StatusResponse(**base_response)

    def _get_status_message(self, status_data: Dict) -> str:
        """Mensagens customizadas por status"""
        status = status_data.get("current", {}).get("status", "")
        
        messages = {
            "Concluído": "Processamento concluído com sucesso!",
            "Erro": "Houve um erro ao processar o arquivo. Tente novamente mais tarde.",
            "Em processamento": "Estamos processando o arquivo. Acompanhe o progresso!"
        }
        
        return messages.get(status, "Status do processamento: " + status)

    def _build_results(self) -> StatusResults:
        """Constrói os links de resultados (extensível)"""
        return StatusResults(
            transcriptions=f"results/{self.conversation_id}/transcriptions",
            pdf_report=f"results/{self.conversation_id}/report",
            analysis_data=f"results/{self.conversation_id}/analysis"
        )