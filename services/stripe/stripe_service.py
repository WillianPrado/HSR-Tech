from __future__ import annotations

import datetime
from typing import Any

import stripe
from fastapi import HTTPException, status

from core.config import settings


class StripeService:
    def __init__(self) -> None:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = settings.STRIPE_API_VERSION

    @staticmethod
    def _to_datetime(timestamp: int | None) -> datetime.datetime | None:
        if timestamp is None:
            return None
        return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)

    def create_or_get_customer(self, *, email: str, name: str | None = None) -> stripe.Customer:
        try:
            existing = stripe.Customer.list(email=email, limit=1)
            if existing and existing.data:
                return existing.data[0]
            return stripe.Customer.create(email=email, name=name)
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe customer error: {exc.user_message or str(exc)}",
            ) from exc

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        user_id: int,
    ) -> stripe.checkout.Session:
        try:
            return stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
                metadata={"user_id": str(user_id), "price_id": price_id},
            )
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe checkout error: {exc.user_message or str(exc)}",
            ) from exc

    def construct_webhook_event(self, payload: bytes, sig_header: str) -> stripe.Event:
        try:
            return stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig_header,
                secret=settings.STRIPE_WEBHOOK_SECRET,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc
        except stripe.error.SignatureVerificationError as exc:
            raise HTTPException(status_code=400, detail="Invalid webhook signature") from exc

    def retrieve_subscription(self, subscription_id: str) -> stripe.Subscription:
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe subscription retrieval error: {exc.user_message or str(exc)}",
            ) from exc

    def cancel_subscription(self, subscription_id: str) -> stripe.Subscription:
        try:
            return stripe.Subscription.cancel(subscription_id)
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe subscription cancel error: {exc.user_message or str(exc)}",
            ) from exc

    def update_subscription_price(
        self,
        *,
        subscription_id: str,
        new_price_id: str,
    ) -> stripe.Subscription:
        subscription = self.retrieve_subscription(subscription_id)
        if not subscription.get("items") or not subscription["items"].get("data"):
            raise HTTPException(status_code=400, detail="Subscription has no updatable items")

        item_id = subscription["items"]["data"][0]["id"]

        try:
            return stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False,
                proration_behavior="create_prorations",
                items=[{"id": item_id, "price": new_price_id}],
            )
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe subscription update error: {exc.user_message or str(exc)}",
            ) from exc

    def list_invoices(self, customer_id: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            invoices = stripe.Invoice.list(customer=customer_id, limit=max(1, min(limit, 50)))
            return list(invoices.data)
        except stripe.error.StripeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Stripe invoice list error: {exc.user_message or str(exc)}",
            ) from exc

    def serialize_subscription_snapshot(self, subscription: stripe.Subscription) -> dict[str, Any]:
        item_price = None
        if subscription.get("items") and subscription["items"].get("data"):
            price = subscription["items"]["data"][0].get("price") or {}
            item_price = price.get("id")

        return {
            "id": subscription.get("id"),
            "status": subscription.get("status"),
            "current_period_start": self._to_datetime(subscription.get("current_period_start")),
            "current_period_end": self._to_datetime(subscription.get("current_period_end")),
            "price_id": item_price,
            "customer": subscription.get("customer"),
        }
