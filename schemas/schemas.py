from typing import Optional, TYPE_CHECKING, List
import datetime
from pydantic import BaseModel, EmailStr, field_validator, Field
import re

if TYPE_CHECKING:
    from models import User

# ============== STRIPE SCHEMAS ==============
class StripeCheckoutRequest(BaseModel):
    """Schema para requisição de criação de checkout session"""
    price_id: str = Field(..., description="ID do preço no Stripe (ex: price_123)")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class StripeSubscriptionResponse(BaseModel):
    """Schema para resposta de assinatura"""
    id: str
    status: str
    current_period_end: datetime.datetime
    plan_id: str

class StripeWebhookEvent(BaseModel):
    """Schema base para eventos do webhook"""
    id: str
    type: str
    created: datetime.datetime

class StripeCustomerCreate(BaseModel):
    """Schema para criação de cliente no Stripe"""
    email: EmailStr
    name: Optional[str] = None
    metadata: Optional[dict] = None

class StripePaymentMethod(BaseModel):
    """Schema para métodos de pagamento"""
    id: str
    card_last4: str
    brand: str
    exp_month: int
    exp_year: int

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    subscription_plan: str = "basic"  # Plano de assinatura (default é "basic")
    full_name: str  # Nome do cliente
    cpf: str  # CPF como string (não mais 'constr')
    whatsapp: Optional[str] = None  # Número do WhatsApp opcional

    # Validador para garantir que o CPF tenha o formato correto
    @field_validator('cpf')
    def validate_cpf(cls, v):
        if not re.match(r'^\d{11}$', v):  # Verifica se o CPF tem exatamente 11 dígitos
            raise ValueError('CPF deve ter 11 dígitos numéricos')
        return v

    # Validador para garantir que o WhatsApp tenha o formato correto
    @field_validator('whatsapp')
    def validate_whatsapp(cls, v):
        if v and not re.match(r'^\+?\d{10,15}$', v):  # Verifica o formato do WhatsApp
            raise ValueError('WhatsApp deve ser um número válido com até 15 dígitos')
        return v

    class Config:
        str_min_length = 1 # Assegura que a string não seja vazia


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
    whatsapp: Optional[str]
    subscription_plan: str
    subscription_status: str
    
    stripe_customer_id: Optional[str] = None 
    payment_methods: List[StripePaymentMethod] = []  
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
