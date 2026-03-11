# dependencies.py
from datetime import UTC, datetime
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from core.http.async_http_client import AsyncHTTPClient
from services.db_handler import get_db
from core.auth import verify_token
from models.user import User
from core.abstractions.illm_client import ILLMClient
from services.reports.llm_factory import get_llm_client as build_llm_client
from services.audio.openai_transcriber import OpenAITranscriber



oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
async def get_http_client() -> AsyncGenerator[AsyncHTTPClient, None]:
    client = AsyncHTTPClient()
    try:
        yield client
    finally:
        await client.close()

async def get_llm_client() -> AsyncGenerator[ILLMClient, None]:
    """
    Dependency that provides a contract-based LLM client instance.
    """
    client = build_llm_client('openai')
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


def _is_subscription_active(user: User) -> bool:
    status_value = getattr(user.subscription_status, "value", user.subscription_status)
    if status_value != "active":
        return False

    if user.subscription_end_date is None:
        return True

    end_date = user.subscription_end_date
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)

    return datetime.now(UTC) <= end_date


def _is_trial_active(user: User) -> bool:
    if user.trial_end_date is None:
        return False

    trial_end = user.trial_end_date
    if trial_end.tzinfo is None:
        trial_end = trial_end.replace(tzinfo=UTC)

    return datetime.now(UTC) <= trial_end


def get_current_paid_user(current_user: User = Depends(get_current_active_user)) -> User:
    is_overdue = _is_subscription_payment_overdue(current_user)
    has_free_credit = _has_free_analysis_credit(current_user)
    if not has_free_credit and current_user.stripe_customer_id is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Credito esgotado. Realize o pagamento ou cadastre sua conta na Stripe.",
        )
    if not is_overdue and current_user.stripe_customer_id is not None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Pagamento em atraso. Regularize sua assinatura para continuar.",
        )

    
    return current_user


def _has_free_analysis_credit(user: User) -> bool:
    return int(getattr(user, "free_analyses_remaining", 0) or 0) > 0


def _is_subscription_payment_overdue(user: User) -> bool:
    status_value = getattr(user.subscription_status, "value", user.subscription_status)
    has_subscription = bool(getattr(user, "stripe_subscription_id", None))
    return has_subscription and status_value in {"suspended", "inactive", "cancelled"}


def enforce_analysis_access(current_user: User) -> User:
    """Validate if the user can request a new analysis without consuming credits yet."""
    if _is_subscription_payment_overdue(current_user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Pagamento em atraso. Regularize sua assinatura para continuar.",
        )

    if _has_free_analysis_credit(current_user):
        return current_user

    if _is_subscription_active(current_user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suas analises acabaram. Compre mais analises para continuar.",
        )

    if _is_trial_active(current_user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Seu limite de analises acabou. Assine um plano ou compre mais analises.",
        )

    has_any_stripe_account = bool(getattr(current_user, "stripe_customer_id", None))
    if not has_any_stripe_account:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suas analises gratis acabaram. Cadastre sua conta na Stripe para continuar.",
        )

    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail="Suas analises gratis acabaram. Realize o pagamento para continuar.",
    )


def consume_analysis_credit(db: Session, user_id: int) -> User:
    """Consume one analysis credit after a successful analysis completion."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not _has_free_analysis_credit(user):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suas analises acabaram. Compre mais analises para continuar.",
        )

    try:
        user.free_analyses_remaining = user.free_analyses_remaining - 1
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to consume free analysis credit",
        ) from exc