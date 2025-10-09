# auth.py
from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from core.config import settings

# Configurações de segurança
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None
    
def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    algorithm: str = "HS256"
) -> str:
    """
    Cria um refresh token JWT com os dados fornecidos.
    
    Args:
        data (dict): Dados a serem incluídos no token (deve conter pelo menos 'sub')
        expires_delta (timedelta, optional): Tempo de expiração do token. Se None, usa o padrão das configurações.
        algorithm (str): Algoritmo de criptografia (padrão: HS256)
    
    Returns:
        str: Refresh token JWT assinado
    
    Raises:
        ValueError: Se os dados não contiverem o campo 'sub'
    """
    if "sub" not in data:
        raise ValueError("O payload do token deve conter o campo 'sub'")
    
    # Configuração do tempo de expiração
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # Payload do token
    to_encode = data.copy()
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh",  # Identifica que é um refresh token
        "jti": generate_jti()  # Identificador único do token
    })
    
    # Geração do token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.REFRESH_TOKEN_SECRET_KEY,
        algorithm=algorithm
    )
    
    return encoded_jwt

def generate_jti() -> str:
    """
    Gera um identificador único para o token (JWT ID)
    
    Returns:
        str: UUID4 como string
    """
    import uuid
    return str(uuid.uuid4())