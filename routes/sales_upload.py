from logging import Logger
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
#from core.dependencies import get_current_user
from core.status_tracker import set_status
from models.user import User
from core.abstractions.ifile_processor import IFileProcessor
from services.sales.whatsapp_processor import WhatsAppSalesProcessor
from services.tasks import process_zip

router = APIRouter(tags=["Sales"])

@router.post("/upload-zip")
async def upload_sales_zip(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    #current_user: User = Depends(get_current_user),
):
    """
    Recebe um ZIP com calls de vendas e processa em background.
    """
    try:
        # Cria diretório temporário se não existir
        zip_path = Path(f"storage/temp_zips/{file.filename}")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Salva o arquivo
        with open(zip_path, "wb") as buffer:
            contents = await file.read()
            buffer.write(contents)
        
        # Inicializa status imediatamente, antes de começar o processamento
        zip_id = file.filename
        await set_status(zip_id, "Upload recebido - aguardando processamento", progress=0)
        
        # Inicia o processamento em background de forma assíncrona
        background_tasks.add_task(process_zip, zip_path)  # Task executada em background
        
        return {"message": "ZIP em processamento", "zip_id": zip_id}
    except Exception as e:
        Logger.error(f"Erro no upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))