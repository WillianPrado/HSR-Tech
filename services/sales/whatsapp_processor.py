from pathlib import Path
from fastapi import HTTPException, UploadFile
from core.abstractions.ifile_processor import IFileProcessor
from core.status_tracker import get_status, set_status
from core.storage.file_validators import FileValidator
from models.user import User
import logging

logger = logging.getLogger(__name__)

class WhatsAppSalesProcessor(IFileProcessor):
    def __init__(self, background_tasks):
        self.background_tasks = background_tasks
    
    async def process_upload(self, file: UploadFile, user: User) -> dict:
        """Implementação específica para WhatsApp"""
        try:
            self._validate_file(file)
            safe_name = FileValidator.sanitize_filename(file.filename)
            save_path = Path(f"storage/temp_zips/{safe_name}")
            
            await self._save_file(file, save_path)
            self._queue_background_task(save_path, user.id)
            zip_id = save_path.name
            await set_status(zip_id, "Upload recebido - aguardando processamento", progress=0)
            return self._build_response(zip_id, user)
            
        except Exception as e:
            logger.error(f"WhatsApp processing error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
    
    def _validate_file(self, file: UploadFile):
        FileValidator.validate_zip_extension(file.filename)
        FileValidator.validate_file_size(file)
    
    async def _save_file(self, file: UploadFile, save_path: str):
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as buffer:
            buffer.write(await file.read())
    
    def _queue_background_task(self, file_path: str, user_id: str):
        from services.tasks import process_zip  # Função que realmente existe
        self.background_tasks.add_task(process_zip, file_path)
    
    def _build_response(self, filename: str, user: User) -> dict:
        zip_id = filename
        return {"message": "ZIP em processamento", "zip_id": zip_id}
    # {
    #         "status": "processing",
    #         "filename": filename,
    #         "user_id": str(user.id),
    #         "service": "whatsapp",
    #         "formats_accepted": [".zip"]
    #     }