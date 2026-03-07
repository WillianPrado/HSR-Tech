from __future__ import annotations

import datetime
import re

from pydantic import BaseModel, EmailStr, field_validator

from schemas.stripe import StripePaymentMethod


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    subscription_plan: str = "basic"
    full_name: str
    cpf: str
    whatsapp: str | None = None

    @field_validator("cpf")
    def validate_cpf(cls, value: str) -> str:
        if not re.match(r"^\d{11}$", value):
            raise ValueError("CPF deve ter 11 dígitos numéricos")
        return value

    @field_validator("whatsapp")
    def validate_whatsapp(cls, value: str | None) -> str | None:
        if value and not re.match(r"^\+?\d{10,15}$", value):
            raise ValueError("WhatsApp deve ser um número válido com até 15 dígitos")
        return value

    class Config:
        str_min_length = 1


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool = True
    created_at: datetime.datetime
    full_name: str
    cpf: str
    whatsapp: str | None
    subscription_plan: str
    subscription_status: str
    free_analyses_remaining: int = 0
    stripe_customer_id: str | None = None
    payment_methods: list[StripePaymentMethod] = []

    class Config:
        from_attributes = True