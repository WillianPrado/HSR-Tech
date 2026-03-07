from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class StripeCheckoutRequest(BaseModel):
    """Schema para requisição de criação de checkout session"""

    price_id: str = Field(..., description="ID do preço no Stripe (ex: price_123)")
    success_url: str | None = None
    cancel_url: str | None = None


class StripeCheckoutResponse(BaseModel):
    """Resposta de checkout hospedado Stripe."""
    price_id: str
    checkout_url: str
    session_id: str


class StripeSubscriptionResponse(BaseModel):
    """Schema para resposta de assinatura"""

    id: str
    status: str
    current_period_end: datetime
    plan_id: str


class StripeWebhookEvent(BaseModel):
    """Schema base para eventos do webhook"""

    id: str
    type: str
    created: datetime


class StripeSubscriptionStatusResponse(BaseModel):
    """Estado consolidado de assinatura do usuario."""

    subscription_plan: str
    subscription_status: str
    trial_end_date: datetime | None = None
    subscription_start_date: datetime | None = None
    subscription_end_date: datetime | None = None
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None


class StripeUpdateSubscriptionRequest(BaseModel):
    """Atualiza o plano da assinatura existente."""

    plan: str = Field(..., description="Plano interno: basic, premium ou enterprise")


class StripeCustomerCreate(BaseModel):
    """Schema para criação de cliente no Stripe"""

    email: EmailStr
    name: str | None = None
    metadata: dict | None = None


class StripePaymentMethod(BaseModel):
    """Schema para métodos de pagamento"""

    id: str
    card_last4: str
    brand: str
    exp_month: int
    exp_year: int


class StripeInvoiceResponse(BaseModel):
    """Item de historico de faturas."""

    stripe_invoice_id: str
    status: str
    amount_due: int | None = None
    amount_paid: int | None = None
    currency: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    hosted_invoice_url: str | None = None
    invoice_pdf: str | None = None
    paid_at: datetime | None = None