from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class StripeCheckoutRequest(BaseModel):
    """Schema para requisição de criação de checkout session"""

    price_id: str = Field(..., description="ID do preço no Stripe (ex: price_123)")
    success_url: str | None = None
    cancel_url: str | None = None


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