from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.config import (
    normalize_price_id,
    settings,
    stripe_price_id_by_plan,
    validate_stripe_runtime_config,
)
from core.dependencies import get_current_active_user
from models.user import SubscriptionPlanEnum, User, UserStatusEnum
from repository.payment_repository import list_invoices_by_user, upsert_invoice
from repository.user_repository import get_user_by_id, update_user_subscription
from schemas.stripe import (
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    StripeInvoiceResponse,
    StripePublicConfigResponse,
    StripeSubscriptionStatusResponse,
    StripeUpdateSubscriptionRequest,
)
from services.db_handler import get_db
from services.stripe.stripe_service import StripeService

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.get("/config", response_model=StripePublicConfigResponse)
def get_stripe_public_config() -> StripePublicConfigResponse:
    return StripePublicConfigResponse(
        stripe_public_key=settings.STRIPE_PUBLIC_KEY,
        payment_success_url=settings.PAYMENT_SUCCESS_URL,
        payment_cancel_url=settings.PAYMENT_CANCEL_URL,
    )


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _price_to_plan_map() -> dict[str, SubscriptionPlanEnum]:
    mapping: dict[str, SubscriptionPlanEnum] = {}
    for plan_name, plan_enum in {
        "basic": SubscriptionPlanEnum.basic,
        "premium": SubscriptionPlanEnum.premium,
        "enterprise": SubscriptionPlanEnum.enterprise,
    }.items():
        price_id = stripe_price_id_by_plan(plan_name)
        if price_id:
            mapping[price_id] = plan_enum
    return mapping


def _plan_from_price_id(price_id: str) -> SubscriptionPlanEnum:
    cleaned_price_id = normalize_price_id(price_id)
    mapping = _price_to_plan_map()
    plan = mapping.get(cleaned_price_id)
    if plan is None:
        raise HTTPException(status_code=400, detail="Price ID is not allowed")
    return plan


def _price_id_for_plan(plan_name: str) -> str:
    price_id = stripe_price_id_by_plan(plan_name)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Missing Stripe price id for plan: {plan_name}")
    return price_id


def _to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _to_status_response(user: User) -> StripeSubscriptionStatusResponse:
    return StripeSubscriptionStatusResponse(
        subscription_plan=_enum_value(user.subscription_plan),
        subscription_status=_enum_value(user.subscription_status),
        trial_end_date=user.trial_end_date,
        subscription_start_date=user.subscription_start_date,
        subscription_end_date=user.subscription_end_date,
        stripe_customer_id=user.stripe_customer_id,
        stripe_subscription_id=user.stripe_subscription_id,
    )


def _sync_user_from_subscription(
    db: Session,
    *,
    user: User,
    subscription: dict[str, Any],
    chosen_plan: SubscriptionPlanEnum | None = None,
) -> User:
    start_date = _to_datetime(subscription.get("current_period_start"))
    end_date = _to_datetime(subscription.get("current_period_end"))

    status_map = {
        "active": UserStatusEnum.active,
        "trialing": UserStatusEnum.active,
        "past_due": UserStatusEnum.suspended,
        "canceled": UserStatusEnum.cancelled,
        "unpaid": UserStatusEnum.suspended,
        "incomplete": UserStatusEnum.inactive,
    }
    stripe_status = subscription.get("status", "inactive")
    local_status = status_map.get(stripe_status, UserStatusEnum.inactive)

    if chosen_plan is None:
        price_id = None
        if subscription.get("items") and subscription["items"].get("data"):
            price = subscription["items"]["data"][0].get("price") or {}
            price_id = price.get("id")
        chosen_plan = _plan_from_price_id(price_id) if price_id else SubscriptionPlanEnum.basic

    return update_user_subscription(
        db,
        user.id,
        {
            "subscription_plan": chosen_plan,
            "subscription_status": local_status,
            "stripe_customer_id": subscription.get("customer"),
            "stripe_subscription_id": subscription.get("id"),
            "subscription_start_date": start_date,
            "subscription_end_date": end_date,
        },
    )


@router.post("/checkout", response_model=StripeCheckoutResponse)
def create_checkout_session(
    request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        validate_stripe_runtime_config()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Avoid duplicate active subscriptions when user retries checkout.
    if current_user.stripe_subscription_id and _enum_value(current_user.subscription_status) == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has an active subscription",
        )

    request_price_id = normalize_price_id(request.price_id)
    chosen_plan = _plan_from_price_id(request_price_id)
    service = StripeService()

    customer_id = current_user.stripe_customer_id
    if not customer_id:
        customer = service.create_or_get_customer(
            email=current_user.email,
            name=current_user.full_name,
        )
        customer_id = customer.get("id")
        update_user_subscription(db, current_user.id, {"stripe_customer_id": customer_id})

    checkout = service.create_checkout_session(
        customer_id=customer_id,
        price_id=request_price_id,
        success_url=request.success_url or settings.PAYMENT_SUCCESS_URL,
        cancel_url=request.cancel_url or settings.PAYMENT_CANCEL_URL,
        user_id=current_user.id,
    )

    # Optimistically keep selected plan before webhook final confirmation.
    update_user_subscription(
        db,
        current_user.id,
        {
            "subscription_plan": chosen_plan,
            "subscription_status": UserStatusEnum.inactive,
        },
    )

    checkout_url = checkout.get("url")
    if not checkout_url:
        raise HTTPException(status_code=502, detail="Stripe checkout URL missing")

    return StripeCheckoutResponse(
        checkout_url=checkout_url,
        session_id=checkout.get("id") or "",
        price_id=request_price_id,
    )


@router.get("/subscription", response_model=StripeSubscriptionStatusResponse)
def get_subscription_status(
    current_user: User = Depends(get_current_active_user),
):
    return _to_status_response(current_user)


@router.post("/cancel-subscription", response_model=StripeSubscriptionStatusResponse)
def cancel_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not current_user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="User has no Stripe subscription")

    service = StripeService()
    subscription = service.cancel_subscription(current_user.stripe_subscription_id)

    updated_user = _sync_user_from_subscription(
        db,
        user=current_user,
        subscription=subscription,
    )
    return _to_status_response(updated_user)


@router.post("/update-subscription", response_model=StripeSubscriptionStatusResponse)
def update_subscription_plan(
    request: StripeUpdateSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not current_user.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="User has no Stripe subscription")

    plan_name = request.plan.lower().strip()
    if plan_name not in {"basic", "premium", "enterprise"}:
        raise HTTPException(status_code=400, detail="Invalid plan")

    price_id = _price_id_for_plan(plan_name)
    service = StripeService()
    subscription = service.update_subscription_price(
        subscription_id=current_user.stripe_subscription_id,
        new_price_id=price_id,
    )

    updated_user = _sync_user_from_subscription(
        db,
        user=current_user,
        subscription=subscription,
        chosen_plan=SubscriptionPlanEnum(plan_name),
    )
    return _to_status_response(updated_user)


@router.get("/invoices", response_model=list[StripeInvoiceResponse])
def list_user_invoices(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if current_user.stripe_customer_id:
        service = StripeService()
        remote_invoices = service.list_invoices(current_user.stripe_customer_id)

        for invoice in remote_invoices:
            lines = invoice.get("lines", {}).get("data", [])
            first_line = lines[0] if lines else {}
            period = first_line.get("period", {}) if first_line else {}

            upsert_invoice(
                db,
                user_id=current_user.id,
                stripe_invoice_id=invoice.get("id"),
                stripe_subscription_id=invoice.get("subscription"),
                status=invoice.get("status") or "unknown",
                amount_due=invoice.get("amount_due"),
                amount_paid=invoice.get("amount_paid"),
                currency=invoice.get("currency"),
                period_start=_to_datetime(period.get("start")),
                period_end=_to_datetime(period.get("end")),
                hosted_invoice_url=invoice.get("hosted_invoice_url"),
                invoice_pdf=invoice.get("invoice_pdf"),
                paid_at=_to_datetime(invoice.get("status_transitions", {}).get("paid_at")),
            )

    rows = list_invoices_by_user(db, user_id=current_user.id)
    return [
        StripeInvoiceResponse(
            stripe_invoice_id=row.stripe_invoice_id,
            status=row.status,
            amount_due=row.amount_due,
            amount_paid=row.amount_paid,
            currency=row.currency,
            period_start=row.period_start,
            period_end=row.period_end,
            hosted_invoice_url=row.hosted_invoice_url,
            invoice_pdf=row.invoice_pdf,
            paid_at=row.paid_at,
        )
        for row in rows
    ]


@router.get("/refresh-subscription", response_model=StripeSubscriptionStatusResponse)
def refresh_subscription_from_stripe(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if not current_user.stripe_subscription_id:
        return _to_status_response(current_user)

    service = StripeService()
    subscription = service.retrieve_subscription(current_user.stripe_subscription_id)
    user = get_user_by_id(db, current_user.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = _sync_user_from_subscription(db, user=user, subscription=subscription)
    return _to_status_response(updated_user)
