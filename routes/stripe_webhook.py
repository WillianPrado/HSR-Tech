from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.config import stripe_price_id_by_plan
from models.user import SubscriptionPlanEnum, UserStatusEnum
from repository.payment_repository import create_payment_event, upsert_invoice
from repository.user_repository import (
    get_user_by_id,
    get_user_by_stripe_customer_id,
    get_user_by_stripe_subscription_id,
    update_user_subscription,
)
from services.db_handler import get_db
from services.stripe.stripe_service import StripeService

router = APIRouter(tags=["Payment"])


def _to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _plan_from_price_id(price_id: str | None) -> SubscriptionPlanEnum:
    mapping: dict[str, SubscriptionPlanEnum] = {}
    for plan_name, enum_value in {
        "basic": SubscriptionPlanEnum.basic,
        "premium": SubscriptionPlanEnum.premium,
        "enterprise": SubscriptionPlanEnum.enterprise,
    }.items():
        configured_price = stripe_price_id_by_plan(plan_name)
        if configured_price:
            mapping[configured_price] = enum_value
    return mapping.get(price_id, SubscriptionPlanEnum.basic)


def _status_from_stripe(status: str | None) -> UserStatusEnum:
    mapping = {
        "active": UserStatusEnum.active,
        "trialing": UserStatusEnum.active,
        "past_due": UserStatusEnum.suspended,
        "canceled": UserStatusEnum.cancelled,
        "unpaid": UserStatusEnum.suspended,
        "incomplete": UserStatusEnum.inactive,
    }
    return mapping.get(status or "", UserStatusEnum.inactive)


def _find_user(db: Session, *, customer_id: str | None, subscription_id: str | None, user_id: int | None):
    if user_id is not None:
        user = get_user_by_id(db, user_id)
        if user:
            return user

    if customer_id:
        user = get_user_by_stripe_customer_id(db, customer_id)
        if user:
            return user

    if subscription_id:
        user = get_user_by_stripe_subscription_id(db, subscription_id)
        if user:
            return user

    return None


def _sync_subscription_to_user(db: Session, user_id: int, subscription: dict[str, Any]) -> None:
    price_id = None
    if subscription.get("items") and subscription["items"].get("data"):
        price = subscription["items"]["data"][0].get("price") or {}
        price_id = price.get("id")

    update_user_subscription(
        db,
        user_id,
        {
            "subscription_plan": _plan_from_price_id(price_id),
            "subscription_status": _status_from_stripe(subscription.get("status")),
            "stripe_customer_id": subscription.get("customer"),
            "stripe_subscription_id": subscription.get("id"),
            "subscription_start_date": _to_datetime(subscription.get("current_period_start")),
            "subscription_end_date": _to_datetime(subscription.get("current_period_end")),
        },
    )


def _extract_user_id(metadata: dict[str, Any] | None) -> int | None:
    if not metadata:
        return None
    user_id = metadata.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    payload = await request.body()
    service = StripeService()
    event = service.construct_webhook_event(payload=payload, sig_header=sig_header)

    data_object = event.get("data", {}).get("object", {})
    event_type = event.get("type") or "unknown"

    customer_id = data_object.get("customer")
    subscription_id = data_object.get("subscription") or data_object.get("id")
    user_id = _extract_user_id(data_object.get("metadata"))

    user = _find_user(
        db,
        customer_id=customer_id,
        subscription_id=subscription_id,
        user_id=user_id,
    )

    if user is None and event_type.startswith("customer.subscription"):
        user = _find_user(
            db,
            customer_id=data_object.get("customer"),
            subscription_id=data_object.get("id"),
            user_id=None,
        )

    stripe_event_id = event.get("id")
    if not stripe_event_id:
        raise HTTPException(status_code=400, detail="Webhook event id is missing")

    inserted = create_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        user_id=user.id if user else None,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        payload=event,
    )
    if inserted is None:
        return {"ok": True, "duplicate": True}

    if event_type == "checkout.session.completed":
        stripe_subscription_id = data_object.get("subscription")
        if stripe_subscription_id and user:
            subscription = service.retrieve_subscription(stripe_subscription_id)
            _sync_subscription_to_user(db, user.id, subscription)

    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        if user:
            _sync_subscription_to_user(db, user.id, data_object)

    elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
        if user:
            lines = data_object.get("lines", {}).get("data", [])
            first_line = lines[0] if lines else {}
            period = first_line.get("period", {}) if first_line else {}

            upsert_invoice(
                db,
                user_id=user.id,
                stripe_invoice_id=data_object.get("id"),
                stripe_subscription_id=data_object.get("subscription"),
                status=data_object.get("status") or "unknown",
                amount_due=data_object.get("amount_due"),
                amount_paid=data_object.get("amount_paid"),
                currency=data_object.get("currency"),
                period_start=_to_datetime(period.get("start")),
                period_end=_to_datetime(period.get("end")),
                hosted_invoice_url=data_object.get("hosted_invoice_url"),
                invoice_pdf=data_object.get("invoice_pdf"),
                paid_at=_to_datetime(data_object.get("status_transitions", {}).get("paid_at")),
            )

            update_user_subscription(
                db,
                user.id,
                {
                    "subscription_status": UserStatusEnum.active
                    if event_type == "invoice.payment_succeeded"
                    else UserStatusEnum.suspended,
                },
            )

    return {"ok": True}
