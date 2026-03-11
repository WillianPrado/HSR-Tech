from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.config import (
    analysis_credits_by_plan,
    normalize_price_id,
    settings,
    stripe_price_id_by_plan,
    validate_stripe_runtime_config,
)
from models.user import SubscriptionPlanEnum, User, UserStatusEnum
from repository.payment_repository import (
    create_payment_event,
    list_invoices_by_user,
    upsert_invoice,
)
from repository.user_repository import (
    get_user_by_id,
    get_user_by_stripe_customer_id,
    get_user_by_stripe_subscription_id,
    update_user_subscription,
)
from schemas.stripe import (
    StripeCheckoutRequest,
    StripeCheckoutResponse,
    StripeInvoiceResponse,
    StripePublicConfigResponse,
    StripeSubscriptionStatusResponse,
)
from services.stripe.stripe_service import StripeService


# ======================================================================
# Pure helpers (no side-effects, no DB)
# ======================================================================

def _to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def _enum_value(value: Any) -> str:
    return getattr(value, "value", value)


def _status_from_stripe(stripe_status: str | None) -> UserStatusEnum:
    mapping = {
        "active": UserStatusEnum.active,
        "trialing": UserStatusEnum.active,
        "past_due": UserStatusEnum.suspended,
        "canceled": UserStatusEnum.cancelled,
        "unpaid": UserStatusEnum.suspended,
        "incomplete": UserStatusEnum.inactive,
    }
    return mapping.get(stripe_status or "", UserStatusEnum.inactive)


def _build_price_plan_map() -> dict[str, SubscriptionPlanEnum]:
    result: dict[str, SubscriptionPlanEnum] = {}
    for plan_name, plan_enum in {
        "basic": SubscriptionPlanEnum.basic,
        "premium": SubscriptionPlanEnum.premium,
        "enterprise": SubscriptionPlanEnum.enterprise,
    }.items():
        configured = stripe_price_id_by_plan(plan_name)
        if configured:
            result[configured] = plan_enum
    return result


def _plan_from_price_id(price_id: str | None) -> SubscriptionPlanEnum:
    """Returns `basic` as fallback when price_id is unknown."""
    return _build_price_plan_map().get(price_id or "", SubscriptionPlanEnum.basic)


def _plan_from_price_id_strict(price_id: str) -> SubscriptionPlanEnum:
    """Raises 400 when price_id is not mapped to any configured plan."""
    plan = _build_price_plan_map().get(normalize_price_id(price_id))
    if plan is None:
        raise HTTPException(status_code=400, detail="Price ID is not allowed")
    return plan


def _price_id_for_plan(plan_name: str) -> str:
    price_id = stripe_price_id_by_plan(plan_name)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Missing Stripe price id for plan: {plan_name}")
    return price_id


def _plan_from_invoice(data_object: dict[str, Any], fallback: SubscriptionPlanEnum) -> SubscriptionPlanEnum:
    lines = data_object.get("lines", {}).get("data", [])
    first_line = lines[0] if lines else {}
    price = first_line.get("price") if first_line else {}
    price_id = (price or {}).get("id") if isinstance(price, dict) else None
    return _plan_from_price_id(price_id) if price_id else fallback


def _extract_user_id(metadata: dict[str, Any] | None) -> int | None:
    if not metadata:
        return None
    try:
        return int(metadata["user_id"])
    except (KeyError, TypeError, ValueError):
        return None


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


# ======================================================================
# Business rules
# ======================================================================

class PaymentUseCases:
    """
    All payment business rules live here.
    Controllers must only call this class — no domain logic in routes/.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.stripe = StripeService()

    # ------------------------------------------------------------------
    # Public config (no auth required, reads only settings)
    # ------------------------------------------------------------------

    @staticmethod
    def get_public_config() -> StripePublicConfigResponse:
        return StripePublicConfigResponse(
            stripe_public_key=settings.STRIPE_PUBLIC_KEY,
            payment_success_url=settings.PAYMENT_SUCCESS_URL,
            payment_cancel_url=settings.PAYMENT_CANCEL_URL,
        )

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def create_checkout(self, user: User, request: StripeCheckoutRequest) -> StripeCheckoutResponse:
        try:
            validate_stripe_runtime_config()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if user.stripe_subscription_id and _enum_value(user.subscription_status) == "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already has an active subscription",
            )

        request_price_id = normalize_price_id(request.price_id)
        chosen_plan = _plan_from_price_id_strict(request_price_id)

        customer_id = user.stripe_customer_id
        if not customer_id:
            customer = self.stripe.create_or_get_customer(email=user.email, name=user.full_name)
            customer_id = customer.get("id")
            update_user_subscription(self.db, user.id, {"stripe_customer_id": customer_id})

        checkout = self.stripe.create_checkout_session(
            customer_id=customer_id,
            price_id=request_price_id,
            success_url=request.success_url or settings.PAYMENT_SUCCESS_URL,
            cancel_url=request.cancel_url or settings.PAYMENT_CANCEL_URL,
            user_id=user.id,
        )

        # Optimistic plan update before webhook final confirmation
        update_user_subscription(
            self.db,
            user.id,
            {"subscription_plan": chosen_plan, "subscription_status": UserStatusEnum.inactive},
        )

        checkout_url = checkout.get("url")
        if not checkout_url:
            raise HTTPException(status_code=502, detail="Stripe checkout URL missing")

        return StripeCheckoutResponse(
            checkout_url=checkout_url,
            session_id=checkout.get("id") or "",
            price_id=request_price_id,
        )

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def get_subscription_status(self, user: User) -> StripeSubscriptionStatusResponse:
        return _to_status_response(user)

    def cancel_subscription(self, user: User) -> StripeSubscriptionStatusResponse:
        if not user.stripe_subscription_id:
            raise HTTPException(status_code=400, detail="User has no Stripe subscription")

        subscription = self.stripe.cancel_subscription(user.stripe_subscription_id)
        updated = self._sync_user_from_subscription(user=user, subscription=subscription)
        return _to_status_response(updated)

    def update_subscription_plan(self, user: User, plan_name: str) -> StripeSubscriptionStatusResponse:
        if not user.stripe_subscription_id:
            raise HTTPException(status_code=400, detail="User has no Stripe subscription")

        plan_name = plan_name.lower().strip()
        if plan_name not in {"basic", "premium", "enterprise"}:
            raise HTTPException(status_code=400, detail="Invalid plan")

        price_id = _price_id_for_plan(plan_name)
        subscription = self.stripe.update_subscription_price(
            subscription_id=user.stripe_subscription_id,
            new_price_id=price_id,
        )
        updated = self._sync_user_from_subscription(
            user=user,
            subscription=subscription,
            chosen_plan=SubscriptionPlanEnum(plan_name),
        )
        return _to_status_response(updated)

    def refresh_subscription(self, user: User) -> StripeSubscriptionStatusResponse:
        if not user.stripe_subscription_id:
            return _to_status_response(user)

        db_user = get_user_by_id(self.db, user.id)
        if db_user is None:
            raise HTTPException(status_code=404, detail="User not found")

        subscription = self.stripe.retrieve_subscription(user.stripe_subscription_id)
        updated = self._sync_user_from_subscription(user=db_user, subscription=subscription)
        return _to_status_response(updated)

    # ------------------------------------------------------------------
    # Invoices
    # ------------------------------------------------------------------

    def list_invoices(self, user: User) -> list[StripeInvoiceResponse]:
        if user.stripe_customer_id:
            for invoice in self.stripe.list_invoices(user.stripe_customer_id):
                lines = invoice.get("lines", {}).get("data", [])
                first_line = lines[0] if lines else {}
                period = first_line.get("period", {}) if first_line else {}
                upsert_invoice(
                    self.db,
                    user_id=user.id,
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

        rows = list_invoices_by_user(self.db, user_id=user.id)
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

    # ------------------------------------------------------------------
    # Webhook processing
    # ------------------------------------------------------------------

    def process_webhook(self, payload: bytes, sig_header: str) -> dict:
        event = self.stripe.construct_webhook_event(payload=payload, sig_header=sig_header)
        data_object = event.get("data", {}).get("object", {})
        event_type = event.get("type") or "unknown"

        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription") or data_object.get("id")
        user_id = _extract_user_id(data_object.get("metadata"))

        user = self._find_user(customer_id=customer_id, subscription_id=subscription_id, user_id=user_id)
        if user is None and event_type.startswith("customer.subscription"):
            user = self._find_user(
                customer_id=data_object.get("customer"),
                subscription_id=data_object.get("id"),
                user_id=None,
            )

        stripe_event_id = event.get("id")
        if not stripe_event_id:
            raise HTTPException(status_code=400, detail="Webhook event id is missing")

        inserted = create_payment_event(
            self.db,
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
            stripe_sub_id = data_object.get("subscription")
            if stripe_sub_id and user:
                subscription = self.stripe.retrieve_subscription(stripe_sub_id)
                self._sync_subscription_to_user(user.id, subscription)

        elif event_type in {
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            if user:
                self._sync_subscription_to_user(user.id, data_object)

        elif event_type in {"invoice.payment_succeeded", "invoice.payment_failed"}:
            if user:
                self._handle_invoice_event(user, event_type, data_object)

        return {"ok": True}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_user(
        self,
        *,
        customer_id: str | None,
        subscription_id: str | None,
        user_id: int | None,
    ) -> User | None:
        if user_id is not None:
            user = get_user_by_id(self.db, user_id)
            if user:
                return user
        if customer_id:
            user = get_user_by_stripe_customer_id(self.db, customer_id)
            if user:
                return user
        if subscription_id:
            user = get_user_by_stripe_subscription_id(self.db, subscription_id)
            if user:
                return user
        return None

    def _sync_user_from_subscription(
        self,
        *,
        user: User,
        subscription: dict[str, Any],
        chosen_plan: SubscriptionPlanEnum | None = None,
    ) -> User:
        start_date = _to_datetime(subscription.get("current_period_start"))
        end_date = _to_datetime(subscription.get("current_period_end"))
        local_status = _status_from_stripe(subscription.get("status", "inactive"))

        if chosen_plan is None:
            price_id = None
            if subscription.get("items") and subscription["items"].get("data"):
                price = subscription["items"]["data"][0].get("price") or {}
                price_id = price.get("id")
            chosen_plan = _plan_from_price_id(price_id) if price_id else SubscriptionPlanEnum.basic

        return update_user_subscription(
            self.db,
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

    def _sync_subscription_to_user(self, user_id: int, subscription: dict[str, Any]) -> None:
        price_id = None
        if subscription.get("items") and subscription["items"].get("data"):
            price = subscription["items"]["data"][0].get("price") or {}
            price_id = price.get("id")

        update_user_subscription(
            self.db,
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

    def _grant_plan_analysis_credits(self, user: User, plan: SubscriptionPlanEnum) -> None:
        credits_to_add = analysis_credits_by_plan(getattr(plan, "value", str(plan)))
        if credits_to_add <= 0:
            return
        current = int(getattr(user, "free_analyses_remaining", 0) or 0)
        user.free_analyses_remaining = current + credits_to_add
        self.db.commit()
        self.db.refresh(user)

    def _handle_invoice_event(self, user: User, event_type: str, data_object: dict[str, Any]) -> None:
        lines = data_object.get("lines", {}).get("data", [])
        first_line = lines[0] if lines else {}
        period = first_line.get("period", {}) if first_line else {}

        upsert_invoice(
            self.db,
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
            self.db,
            user.id,
            {
                "subscription_status": (
                    UserStatusEnum.active
                    if event_type == "invoice.payment_succeeded"
                    else UserStatusEnum.suspended
                )
            },
        )

        if event_type == "invoice.payment_succeeded":
            fallback_plan = getattr(user, "subscription_plan", SubscriptionPlanEnum.basic)
            invoice_plan = _plan_from_invoice(data_object, fallback_plan)
            self._grant_plan_analysis_credits(user, invoice_plan)
