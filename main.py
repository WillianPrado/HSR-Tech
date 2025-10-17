# backend/main.py
"""
Main FastAPI entrypoint for IA Chat & Sales Analyzer.
Provides automatic Swagger documentation and integrates
upload, report, authentication, and status services.

Author: Willian Prado
Version: 1.0.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import sales_upload, report_service, status_service, auth
import logging
from logging.config import dictConfig


# ==============================================================
# FASTAPI APPLICATION SETUP
# ==============================================================

app = FastAPI(
    title="IA Chat & Sales Analyzer API",
    description=(
        "Intelligent backend that automates the extraction, transcription, "
        "and analysis of WhatsApp conversations and voice messages for "
        "sales performance insights.\n\n"
        "🚀 Features:\n"
        "- Upload ZIP files with chats and audios\n"
        "- Automatic transcription via OpenAI\n"
        "- PDF report generation with insights\n"
        "- Real-time processing status tracking"
    ),
    version="1.0.0",
    contact={
        "name": "Willian Prado",
        "url": "https://github.com/WillianPrado",
        "email": "contato@willianprado.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)


# ==============================================================
# MIDDLEWARE (CORS)
# ==============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================
# ROOT ENDPOINT
# ==============================================================

@app.get("/", tags=["Root"])
def read_root():
    """Health check endpoint."""
    return {"message": "Welcome to IA Chat & Sales Analyzer API"}


# ==============================================================
# ROUTER REGISTRATION
# ==============================================================

# All routers grouped under /api/v1 for versioning clarity
app.include_router(sales_upload.router, prefix="/api/v1", tags=["Uploads"])
app.include_router(report_service.router, prefix="/api/v1", tags=["Reports"])
app.include_router(status_service.router, prefix="/api/v1", tags=["Status"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])


# ==============================================================
# LOGGING CONFIGURATION
# ==============================================================

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "INFO",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "app.log",
            "formatter": "default",
            "level": "DEBUG",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

dictConfig(logging_config)
