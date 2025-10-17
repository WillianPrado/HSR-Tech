# models/user.py
import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.orm import declarative_base
import enum

Base = declarative_base()

class UserStatusEnum(enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    cancelled = "cancelled"

class SubscriptionPlanEnum(enum.Enum):
    free = "free"
    basic = "basic"
    premium = "premium"
    enterprise = "enterprise"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True)
    hashed_password = Column(String(128))
    full_name = Column(String(100))
    cpf = Column(String(11))
    whatsapp = Column(String(20))
    subscription_plan = Column(Enum(SubscriptionPlanEnum), default=SubscriptionPlanEnum.free)
    subscription_status = Column(Enum(UserStatusEnum), default=UserStatusEnum.inactive)
    created_at = Column(DateTime, default=datetime.datetime.now())
    subscription_start_date = Column(DateTime, nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    last_access = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(100), nullable=True, unique=True)
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    trial_end_date = Column(DateTime, nullable=True)
    
    def is_subscription_active(self):
        if self.subscription_status == UserStatusEnum.active:
            if self.subscription_end_date and datetime.datetime.now() < self.subscription_end_date:
                return True
        return False