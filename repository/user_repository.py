# sele_analytics_back_end\backend\crud.py
from datetime import datetime, timedelta, UTC  
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from models.user import User, UserStatusEnum, SubscriptionPlanEnum
from schemas.user import UserCreate
from core.auth import get_password_hash, verify_password


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Obtém um usuário pelo id."""
    try:
        return db.query(User).filter(User.id == user_id).first()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching user by id"
        ) from e

def get_user_by_email(db: Session, email: str) -> User | None:
    """Obtém um usuário pelo email."""
    try:
        return db.query(User).filter(User.email == email).first()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching user"
        ) from e

def get_user_by_stripe_customer_id(db: Session, stripe_customer_id: str) -> User | None:
    """Obtém um usuário pelo ID do cliente no Stripe."""
    try:
        return db.query(User).filter(User.stripe_customer_id == stripe_customer_id).first()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching user by Stripe ID"
        ) from e

def get_user_by_stripe_subscription_id(db: Session, stripe_subscription_id: str) -> User | None:
    """Obtém um usuário pelo ID da assinatura no Stripe."""
    try:
        return db.query(User).filter(User.stripe_subscription_id == stripe_subscription_id).first()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while fetching user by subscription ID"
        ) from e

def create_user(db: Session, user_data: UserCreate) -> User:
    """Cria um novo usuário com status inicial e plano padrão."""
    try:
        # Verifica se o usuário já existe
        if get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        hashed_password = get_password_hash(user_data.password)
        
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            cpf=user_data.cpf,
            whatsapp=user_data.whatsapp,
            subscription_plan=SubscriptionPlanEnum.free,  # Plano padrão
            subscription_status=UserStatusEnum.inactive,  # Inicia como inativo
            created_at=datetime.now(UTC),
            is_active=True,
            free_analyses_remaining=2,
            # Campos de assinatura serão preenchidos após o checkout no Stripe
            stripe_customer_id=None,
            stripe_subscription_id=None,
            subscription_start_date=None,
            subscription_end_date=None,
            trial_end_date=datetime.now(UTC) + timedelta(days=14)  # Período de teste de 14 dias
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
        
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating user"
        ) from e

def authenticate_user(db: Session, email: str, password: str) -> User:
    """Autentica um usuário e verifica se a assinatura está ativa."""
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verifica se o usuário está ativo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Atualiza o último acesso
    try:
        user.last_access = datetime.now(UTC)
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        # Não interrompe o fluxo por falha na atualização do último acesso
    
    return user

def update_user(db: Session, user_id: int, update_data: dict) -> User:
    """Atualiza os dados do usuário."""
    try:
        user = get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        db.commit()
        db.refresh(user)
        return user
        
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while updating user"
        ) from e

def update_user_subscription(
    db: Session,
    user_id: int,
    subscription_data: dict
) -> User:
    """Atualiza os dados de assinatura do usuário."""
    valid_fields = {
        'subscription_plan',
        'subscription_status',
        'stripe_customer_id',
        'stripe_subscription_id',
        'subscription_start_date',
        'subscription_end_date',
        'trial_end_date'
    }
    
    filtered_data = {
        k: v for k, v in subscription_data.items()
        if k in valid_fields
    }
    
    return update_user(db, user_id, filtered_data)