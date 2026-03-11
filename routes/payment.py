from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.dependencies import get_current_active_user
from models.user import User
from schemas.stripe import (
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    StripeInvoiceResponse,
    StripePublicConfigResponse,
    StripeSubscriptionStatusResponse,
    StripeUpdateSubscriptionRequest,
)
from services.db_handler import get_db
from services.stripe.payment_use_cases import PaymentUseCases

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.get("/config", response_model=StripePublicConfigResponse)
def get_stripe_public_config() -> StripePublicConfigResponse:
    return PaymentUseCases.get_public_config()


@router.post("/checkout", response_model=StripeCheckoutResponse)
def create_checkout_session(
    request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StripeCheckoutResponse:
    return PaymentUseCases(db).create_checkout(current_user, request)


@router.get("/subscription", response_model=StripeSubscriptionStatusResponse)
def get_subscription_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StripeSubscriptionStatusResponse:
    return PaymentUseCases(db).get_subscription_status(current_user)


@router.post("/cancel-subscription", response_model=StripeSubscriptionStatusResponse)
def cancel_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StripeSubscriptionStatusResponse:
    return PaymentUseCases(db).cancel_subscription(current_user)


@router.post("/update-subscription", response_model=StripeSubscriptionStatusResponse)
def update_subscription_plan(
    request: StripeUpdateSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StripeSubscriptionStatusResponse:
    return PaymentUseCases(db).update_subscription_plan(current_user, request.plan)


@router.get("/invoices", response_model=list[StripeInvoiceResponse])
def list_user_invoices(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> list[StripeInvoiceResponse]:
    return PaymentUseCases(db).list_invoices(current_user)


@router.get("/refresh-subscription", response_model=StripeSubscriptionStatusResponse)
def refresh_subscription_from_stripe(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StripeSubscriptionStatusResponse:
    return PaymentUseCases(db).refresh_subscription(current_user)
