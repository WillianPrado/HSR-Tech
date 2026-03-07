import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
from uuid import UUID, uuid4
from mysqlx import Session
#from core.dependencies import get_current_user
from core.dependencies import get_current_paid_user, get_current_user
from core.status_tracker import set_status
from models.user import User
from repository.conversation_repository import create_conversation
from services.db_handler import get_db
from services.tasks import process_zip

router = APIRouter(tags=["Sales"])
logger = logging.getLogger(__name__)

@router.post("/upload-zip")
async def upload_sales_zip(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_paid_user),
    db: Session = Depends(get_db)
):
    """
    Recebe um ZIP com calls de vendas e processa em background.
    """
    try:
        conversation_id = str(uuid4())

        # Cria diretório temporário se não existir
        safe_name = Path(file.filename).name
        zip_path = Path(f"storage/temp_zips/{conversation_id}_{safe_name}")
        zip_path.parent.mkdir(parents=True, exist_ok=True)

        create_conversation(
            db=db,
            user_id=current_user.id,
            conversation_id=UUID(conversation_id),
            title=f"Análise {safe_name}",
            transcript="",
            audio_path=str(zip_path),
        )
        
        # Salva o arquivo
        with open(zip_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)
        
        # Inicializa status imediatamente, antes de começar o processamento
        await set_status(conversation_id, "Upload recebido - aguardando processamento", progress=0)
        
        # Inicia o processamento em background de forma assíncrona
        background_tasks.add_task(process_zip, zip_path, current_user.id, db, conversation_id)  # Task executada em background
        
        return {
            "message": "ZIP em processamento",
            "conversation_id": conversation_id,
        }
    except Exception as e:
        logger.error(f"Erro no upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))