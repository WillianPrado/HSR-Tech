"""add payment events and invoices

Revision ID: 9f83bff4d6a1
Revises: 7b34e3ada0c4
Create Date: 2026-03-07 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "9f83bff4d6a1"
down_revision: Union[str, Sequence[str], None] = "7b34e3ada0c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("payment_events"):
        op.create_table(
            "payment_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("stripe_event_id", sa.String(length=120), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("stripe_customer_id", sa.String(length=120), nullable=True),
            sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("stripe_event_id"),
        )

    if not inspector.has_table("invoices"):
        op.create_table(
            "invoices",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("stripe_invoice_id", sa.String(length=120), nullable=False),
            sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("amount_due", sa.Integer(), nullable=True),
            sa.Column("amount_paid", sa.Integer(), nullable=True),
            sa.Column("currency", sa.String(length=12), nullable=True),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
            sa.Column("hosted_invoice_url", sa.String(length=500), nullable=True),
            sa.Column("invoice_pdf", sa.String(length=500), nullable=True),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("stripe_invoice_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("invoices"):
        op.drop_table("invoices")

    if inspector.has_table("payment_events"):
        op.drop_table("payment_events")
