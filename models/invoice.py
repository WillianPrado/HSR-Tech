import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from models.user import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stripe_invoice_id = Column(String(120), nullable=False, unique=True)
    stripe_subscription_id = Column(String(120), nullable=True)
    status = Column(String(40), nullable=False)
    amount_due = Column(Integer, nullable=True)
    amount_paid = Column(Integer, nullable=True)
    currency = Column(String(12), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    hosted_invoice_url = Column(String(500), nullable=True)
    invoice_pdf = Column(String(500), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
