from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.user import User
from services.db_handler import get_db
from schemas.schemas import UserCreate, UserResponse, Token
from repository.user_repository import create_user, authenticate_user, get_user_by_email
from core.auth import create_access_token, create_refresh_token
from core.dependencies import get_current_active_user
from core.config import settings
#from services.email_service import send_confirmation_email

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

# Exceções personalizadas
class EmailAlreadyRegisteredError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado",
            headers={"WWW-Authenticate": "Bearer"}
        )

class InvalidCredentialsError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post(
    "/register",
    response_model=UserResponse,
    responses={
        400: {"description": "Email já cadastrado ou dados inválidos"},
        422: {"description": "Erro de validação dos dados de entrada"},
        500: {"description": "Erro interno no servidor"}
    },
    summary="Registrar novo usuário",
    description="""
    Endpoint para registro de novos usuários no sistema.
    
    Requisitos:
    - Email válido e não cadastrado anteriormente
    - Senha com pelo menos 8 caracteres
    - CPF válido
    """
)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        # Validações
        if len(user.password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A senha deve ter pelo menos 8 caracteres"
            )
            
        db_user = get_user_by_email(db, email=user.email)
        if db_user:
            logger.warning(f"Tentativa de registro com email já cadastrado: {user.email}")
            raise EmailAlreadyRegisteredError()
        
        new_user = create_user(db=db, user_data=user)
        
        # Enviar email de confirmação
        # try:
        #     send_confirmation_email(new_user.email)
        #     logger.info(f"Email de confirmação enviado para: {user.email}")
        # except Exception as e:
        #     logger.error(f"Falha ao enviar email de confirmação: {str(e)}")
        
        logger.info(f"Novo usuário registrado: {user.email}")
        return new_user
        
    except Exception as e:
        logger.error(f"Erro no registro: {str(e)}")
        raise

@router.post(
    "/login",
    response_model=Token,
    responses={
        401: {"description": "Credenciais inválidas"},
        429: {"description": "Muitas tentativas de login"},
        500: {"description": "Erro interno no servidor"}
    },
    summary="Autenticar usuário",
    description="Endpoint para autenticação de usuários e obtenção de tokens JWT."
)
@limiter.limit("5/minute")
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    try:
        user = authenticate_user(db, form_data.username, form_data.password)
        if not user:
            logger.warning(f"Tentativa de login falha para: {form_data.username}")
            raise InvalidCredentialsError()
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        access_token = create_access_token(
            data={"sub": user.email, "scopes": form_data.scopes},
            expires_delta=access_token_expires
        )
        refresh_token = create_refresh_token(
            data={"sub": user.email},
            expires_delta=refresh_token_expires
        )
        
        logger.info(f"Login bem-sucedido para: {user.email}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        logger.error(f"Erro no login: {str(e)}")
        raise

@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"description": "Credenciais inválidas ou ausentes"},
        403: {"description": "Usuário inativo ou sem permissões"},
    },
    summary="Obter informações do usuário atual",
    description="Endpoint para recuperar informações do usuário autenticado."
)
def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user