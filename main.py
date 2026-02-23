# main.py
"""
Main FastAPI entrypoint for AI Chat & Sales Analyzer.
Provides automatic Swagger documentation and integrates
upload, report, authentication, and status services.

Author: Willian Prado
Version: 1.0.0
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import time
import logging
import re
from logging.config import dictConfig
from contextlib import asynccontextmanager
from datetime import datetime
import sys
import os
from services.db_handler import init_db

# Import routers
from routes import sales_upload, report_service, status_service, auth, analysis_service, conversation_service

# ==============================================================
# UNICODE FIX FOR WINDOWS
# ==============================================================

def setup_unicode_support():
    """Fix Unicode encoding issues on Windows."""
    if sys.platform == "win32":
        # Configure stdout for UTF-8 on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')

setup_unicode_support()

# ==============================================================
# LIFESPAN MANAGEMENT (FastAPI 0.104+)
# ==============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    # Startup - usando texto simples para evitar problemas de Unicode
    logging.info("Starting AI Chat & Sales Analyzer API...")
    logging.info("Initializing services...")
    init_db()
    logging.info("Database initialized")
    
    yield
    
    # Shutdown
    logging.info("Shutting down AI Chat & Sales Analyzer API...")
    logging.info("Cleaning up resources...")

# ==============================================================
# FASTAPI APPLICATION SETUP
# ==============================================================

app = FastAPI(
    title="IA Chat & Sales Analyzer API",
    description=(
        "Intelligent backend that automates the extraction, transcription, "
        "and analysis of WhatsApp conversations and voice messages for "
        "sales performance insights.\n\n"
        "🚀 **Features:**\n"
        "- 📁 Upload ZIP files with chats and audios\n"
        "- 🎙️ Automatic transcription via OpenAI\n"
        "- 📊 PDF report generation with insights\n"
        "- 🔍 Real-time processing status tracking\n"
        "- 🔐 JWT Authentication & Security\n"
        "- 📈 Performance monitoring\n\n"
        "**Tech Stack:** FastAPI, Python, OpenAI, SQL, JWT"
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
# MIDDLEWARE CONFIGURATION
# ==============================================================

def _normalize_origin(origin: str) -> str:
    cleaned = origin.strip().strip('"').strip("'")
    if cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    return cleaned

# CORS origins from environment (comma-separated)
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [_normalize_origin(origin) for origin in allowed_origins_env.split(",") if _normalize_origin(origin)]

if not allowed_origins:
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "https://sele-analytics.netlify.app",
    ]

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://([a-z0-9-]+\.)?netlify\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Custom middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests and response times."""
    start_time = time.time()
    
    # Log request - sem emojis para compatibilidade
    logging.info(f"INCOMING {request.method} {request.url} - Client: {request.client.host}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response with timing
        logging.info(
            f"OUTGOING {request.method} {request.url} "
            f"- Status: {response.status_code} "
            f"- Duration: {process_time:.4f}s"
        )
        
        # Add performance header
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response
        
    except Exception as ex:
        process_time = time.time() - start_time
        logging.error(
            f"ERROR {request.method} {request.url} "
            f"- Error: {str(ex)} "
            f"- Duration: {process_time:.4f}s"
        )
        raise

# ==============================================================
# EXCEPTION HANDLERS
# ==============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom handler for validation errors."""
    logging.warning(f"VALIDATION ERROR: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors(),
            "body": exc.body
        },
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    """Custom handler for internal server errors."""
    logging.error(f"INTERNAL SERVER ERROR: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": "An unexpected error occurred. Please try again later."
        },
    )

# ==============================================================
# ROOT & HEALTH CHECK ENDPOINTS
# ==============================================================

@app.get("/", tags=["System"])
async def read_root():
    """Health check and API information endpoint."""
    return {
        "message": "Welcome to AI Chat & Sales Analyzer API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "developer": "Willian Prado",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health", tags=["System"])
async def health_check():
    """Comprehensive health check endpoint for monitoring."""
    try:
        import psutil
        
        system_info = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
        }
    except ImportError:
        system_info = {"message": "psutil not available"}
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "system": system_info,
        "services": {
            "api": "operational",
            "database": "operational",
            "openai": "operational"
        }
    }

@app.get("/api/v1/info", tags=["System"])
async def api_info():
    """Detailed API information endpoint."""
    return {
        "api": {
            "name": "AI Chat & Sales Analyzer API",
            "version": "1.0.0",
            "description": "Intelligent sales conversation analysis platform",
            "developer": "Willian Prado"
        },
        "features": [
            "ZIP file upload with chat and audio processing",
            "OpenAI-powered transcription",
            "PDF report generation",
            "Real-time status tracking",
            "JWT authentication"
        ],
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/api/v1/openapi.json"
        }
    }

# ==============================================================
# ROUTER REGISTRATION
# ==============================================================

# All routers grouped under /api/v1 for versioning clarity
app.include_router(sales_upload.router, prefix="/api/v1", tags=["Uploads"])
app.include_router(report_service.router, prefix="/api/v1", tags=["Reports"])
app.include_router(status_service.router, prefix="/api/v1", tags=["Status"])
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])
app.include_router(analysis_service.router, prefix="/api/v1", tags=["Analysis"])
app.include_router(conversation_service.router, prefix="/api/v1", tags=["Conversations"])

# ==============================================================
# LOGGING CONFIGURATION (UNICODE SAFE)
# ==============================================================

class UnicodeSafeStreamHandler(logging.StreamHandler):
    """Custom stream handler that handles Unicode encoding issues."""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            # Fallback: remove non-ASCII characters
            safe_msg = record.getMessage().encode('ascii', 'ignore').decode('ascii')
            record.msg = safe_msg
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        },
        "detailed": {
            "format": "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "()": UnicodeSafeStreamHandler,  # Use our custom handler
            "formatter": "default",
            "level": "INFO",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "app.log",
            "formatter": "detailed",
            "level": "DEBUG",
            "encoding": "utf-8",  # Ensure file uses UTF-8
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

dictConfig(logging_config)

# ==============================================================
# APPLICATION STARTUP MESSAGE
# ==============================================================

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting AI Chat & Sales Analyzer API server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )