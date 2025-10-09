# backend/core/status_tracker.pyfrom datetime import datetime
from typing import Dict
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime  

# Armazena o status de cada tarefa
_status_store: Dict[str, Dict[str, any]] = {}
_lock = asyncio.Lock()

@asynccontextmanager
async def status_lock():
    """Async lock com timeout para evitar concorrência no acesso ao _status_store."""
    try:
        await asyncio.wait_for(_lock.acquire(), timeout=1.0)
        yield
    finally:
        if _lock.locked():
            _lock.release()

async def set_status(zip_id: str, status: str, progress: float = None):
    """Atualiza o status do processamento de forma assíncrona."""
    async with status_lock():
        if zip_id not in _status_store:
            _status_store[zip_id] = {
                "created_at": datetime.now().isoformat(),
                "history": []
            }

        # Se o status for None, substitua por um valor padrão
        if status is None:
            status = "Indefinido"
        
        # Cria um novo entry de status
        entry = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "progress": progress
        }

        _status_store[zip_id]["current"] = entry
        _status_store[zip_id]["history"].append(entry)

async def get_status(zip_id: str) -> Dict[str, any]:
    """Recupera o status do processamento."""
    try:
        async with status_lock():
            if zip_id not in _status_store:
                return {"status": "not_found"}  # Retorna uma resposta padrão se o status não for encontrado
            
            return _status_store[zip_id]
    except asyncio.TimeoutError:
        return {"status": "timeout", "message": "System busy"}
