# services/chat/chat_file_handler.py
import re
from pathlib import Path
from typing import Dict

from typing import Dict
import aiofiles

class ChatProcessor:
    def find_audio_files(self, chat_content: str) -> list[Path]:
        return [Path(file) for file in re.findall(r"[\w-]+\.opus", chat_content)]

    async def update_chat_file(self, chat_path: Path, transcriptions: Dict[str, str]) -> None:
        """Atualiza o arquivo de chat com as transcrições de forma assíncrona"""
        async with aiofiles.open(chat_path, "r+", encoding="utf-8") as file:
            lines = await file.readlines()
            await file.seek(0)
            
            for line in lines:
                await file.write(line)
                if match := re.search(r"([\w-]+\.opus)", line):
                    audio_file = match.group(1)
                    if audio_file in transcriptions:
                        await file.write(f"TRANSCRIÇÃO: {transcriptions[audio_file]}\n")