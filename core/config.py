from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Carrega variáveis do .env antes da configuração
load_dotenv()

class Settings(BaseSettings):
    
    OPENAI_API_KEY: str
    DEEP_SEEK_API_KEY: str
    STRIPE_SECRET_KEY: str
    
    DATABASE_URL: str = "sqlite:///./sales.db"
    PYTHONPATH: str | None = None 
    SECRET_KEY: str 
    ALGORITHM: str 
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_SECRET_KEY: str = "segredo"
    MAX_CONCURRENT_TRANSCRIPTIONS: int = 2
    TRANSCRIPTION_RETRY_ATTEMPTS: int = 5
    TRANSCRIPTION_RETRY_MIN_WAIT_SECONDS: int = 2
    TRANSCRIPTION_RETRY_MAX_WAIT_SECONDS: int = 30
   
   
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  
        case_sensitive=False 
        
    )


settings = Settings()