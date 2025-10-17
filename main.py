from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import sales_upload, report_service, status_service, auth
import logging
from logging.config import dictConfig

# ⚠️ APENAS ESTA INSTÂNCIA - REMOVA A OUTRA!
app = FastAPI(
    title="Sele Analytics API",
    description="API para processamento de análises de vendas",
    version="1.0.0",
    timeout=300,
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"Hello": "World"}

# Routers
app.include_router(sales_upload.router, prefix="/api/v1")
app.include_router(report_service.router, prefix="/api/v1")
app.include_router(status_service.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")

# Logging (mantenha igual)
logging_config = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message%s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "INFO"
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "app.log",
            "formatter": "default",
            "level": "DEBUG"
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO"
    }
}

dictConfig(logging_config)