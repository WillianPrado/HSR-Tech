from __future__ import annotations

import datetime
import logging
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from models.invoice import Invoice
from models.payment_event import PaymentEvent

logger = logging.getLogger(__name__)


def get_payment_event_by_stripe_id(db: Session, stripe_event_id: str) -> PaymentEvent | None:
    try:
        return (
            db.query(PaymentEvent)
            .filter(PaymentEvent.stripe_event_id == stripe_event_id)
            .first()
        )
    except SQLAlchemyError:
        logger.exception("Database error while fetching payment event")
        raise


def create_payment_event(
    db: Session,
    *,
    stripe_event_id: str,
    event_type: str,
    user_id: int | None,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    payload: dict[str, Any] | None,
) -> PaymentEvent | None:
    event = PaymentEvent(
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        user_id=user_id,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        payload=payload,
        processed_at=datetime.datetime.now(datetime.timezone.utc),
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    except IntegrityError:
        db.rollback()
        return None
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while creating payment event")
        raise


def upsert_invoice(
    db: Session,
    *,
    user_id: int,
    stripe_invoice_id: str,
    stripe_subscription_id: str | None,
    status: str,
    amount_due: int | None,
    amount_paid: int | None,
    currency: str | None,
    period_start: datetime.datetime | None,
    period_end: datetime.datetime | None,
    hosted_invoice_url: str | None,
    invoice_pdf: str | None,
    paid_at: datetime.datetime | None,
) -> Invoice:
    try:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.stripe_invoice_id == stripe_invoice_id)
            .first()
        )

        if invoice is None:
            invoice = Invoice(
                user_id=user_id,
                stripe_invoice_id=stripe_invoice_id,
                stripe_subscription_id=stripe_subscription_id,
                status=status,
                amount_due=amount_due,
                amount_paid=amount_paid,
                currency=currency,
                period_start=period_start,
                period_end=period_end,
                hosted_invoice_url=hosted_invoice_url,
                invoice_pdf=invoice_pdf,
                paid_at=paid_at,
            )
            db.add(invoice)
        else:
            invoice.user_id = user_id
            invoice.stripe_subscription_id = stripe_subscription_id
            invoice.status = status
            invoice.amount_due = amount_due
            invoice.amount_paid = amount_paid
            invoice.currency = currency
            invoice.period_start = period_start
            invoice.period_end = period_end
            invoice.hosted_invoice_url = hosted_invoice_url
            invoice.invoice_pdf = invoice_pdf
            invoice.paid_at = paid_at

        db.commit()
        db.refresh(invoice)
        return invoice
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Database error while upserting invoice")
        raise


def list_invoices_by_user(db: Session, user_id: int, limit: int = 30) -> list[Invoice]:
    safe_limit = max(1, min(limit, 100))
    try:
        return (
            db.query(Invoice)
            .filter(Invoice.user_id == user_id)
            .order_by(Invoice.created_at.desc())
            .limit(safe_limit)
            .all()
        )
    except SQLAlchemyError:
        logger.exception("Database error while listing invoices")
        raise
