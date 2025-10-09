# backend\services\audio\openai_transcriber.py
import asyncio
import aiohttp
import requests
from abc import ABC, abstractmethod
import os
import subprocess
from pathlib import Path
from core.config import settings
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

# Configuração de logging
logger = logging.getLogger(__name__)

class Transcriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        pass
import subprocess

def convert_opus_to_mp3(input_path: str) -> str:
    """Converte arquivo OPUS para MP3 com tratamento de erros completo"""
    try:
        input_path = Path(input_path).resolve()
        logger.debug(f"Iniciando conversão de: {input_path}")

        if not input_path.exists():
            raise FileNotFoundError(f"Arquivo OPUS não encontrado: {input_path}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / f"{input_path.stem}.mp3"
            
            # Comando FFmpeg como lista de argumentos
            cmd = [
                'ffmpeg',
                '-y',  # Sobrescrever automaticamente
                '-i', str(input_path),
                '-acodec', 'libmp3lame',
                '-loglevel', 'error',
                str(output_path)
            ]
            
            # Executa com timeout usando subprocess
            subprocess.run(
                cmd,
                check=True,
                timeout=30,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            if not output_path.exists():
                raise RuntimeError(f"Falha na conversão: {output_path} não gerado")
                
            return str(output_path)

    except subprocess.TimeoutExpired as e:
        logger.error(f"Timeout na conversão: {str(e)}")
        raise
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro FFmpeg (code {e.returncode}): {e.stderr.decode().strip()}")
        raise
    except Exception as e:
        logger.error(f"Erro inesperado: {str(e)}", exc_info=True)
        raise



class OpenAITranscriber(Transcriber):
    def __init__(self, api_key: str = settings.OPENAI_API_KEY, model: str = "whisper-1"):
        if not api_key: 
            raise ValueError("OPENAI_API_KEY não configurada")
        self.api_key = api_key
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def transcribe(self, audio_path: str) -> str:  # Adicione async aqui
        """Transcreve áudio usando OpenAI Whisper totalmente em memória"""
        try:
            audio_path = Path(audio_path).resolve()
            
            if not audio_path.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")

            # Executa o FFmpeg em um executor de thread (para não bloquear)
            loop = asyncio.get_event_loop()
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-f', 'mp3',
                '-acodec', 'libmp3lame',
                '-loglevel', 'error',
                'pipe:1'
            ]

            # Executa o processo de forma assíncrona
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            )
            
            # Comunicação assíncrona
            audio_data, stderr_data = await loop.run_in_executor(
                None,
                process.communicate,
                None,
                30  # timeout
            )
            
            if process.returncode != 0:
                raise RuntimeError(f"Erro FFmpeg: {stderr_data.decode().strip()}")

            # Requisição HTTP assíncrona
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('file', audio_data, filename='audio.mp3', content_type='audio/mpeg')
                data.add_field('model', self.model)
                
                async with session.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=data,
                    timeout=30
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result.get("text", "")

        except Exception as e:
            logger.error(f"Erro na transcrição: {str(e)}", exc_info=True)
            raise
# Exemplo de uso:
# transcriber = OpenAITranscriber()  # Pega a chave automaticamente do settings
# text = transcriber.transcribe("audio.opus")