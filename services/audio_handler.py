import os
from pathlib import Path
import subprocess
from datetime import datetime
from fastapi import UploadFile 

async def process_audio(file: UploadFile) -> dict:
    temp_dir = Path("temp_audios")
    temp_dir.mkdir(exist_ok=True)
    
    file_path = temp_dir / f"teste{datetime.now().timestamp()}.opus"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    mp3_path = file_path.with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-i", str(file_path), str(mp3_path)], check=True)
    
    return {"message": "Áudio recebido", "path": str(mp3_path)}