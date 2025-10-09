import logging
from pathlib import Path
import os
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = "sele_analytics"):
    # Configuração básica
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Captura tudo desde DEBUG
    
    # Formato padrão
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Só mostra INFO+ no console
    console_handler.setFormatter(formatter)
    
    # Handler para arquivo (com rotação)
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Remove handlers existentes (evita duplicação)
    if logger.handlers:
        logger.handlers.clear()
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger