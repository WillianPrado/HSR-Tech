# backend/dependencies.py
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from core.http.async_http_client import AsyncHTTPClient
from services.db_handler import get_db
from core.auth import verify_token
from models.user import User
from services.reports.deepseek_client import DeepSeekClient
from services.audio.openai_transcriber import OpenAITranscriber



oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
async def get_http_client() -> AsyncGenerator[AsyncHTTPClient, None]:
    client = AsyncHTTPClient()
    try:
        yield client
    finally:
        await client.close()

async def get_llm_client() -> AsyncGenerator[DeepSeekClient, None]:
    """
    Dependency that provides DeepSeekClient instance.
    """
    client = DeepSeekClient()
    try:
        yield client
    finally:
        await client.close()
async def get_transcriber(http_client: AsyncHTTPClient = Depends(get_http_client)) -> OpenAITranscriber:
    return OpenAITranscriber(http_client)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    from repository.user_repository import get_user_by_email
    
    email = verify_token(token)
    if email is None:
        raise credentials_exception
    
    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user