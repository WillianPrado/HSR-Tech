"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-02-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=100), nullable=True),
            sa.Column("hashed_password", sa.String(length=128), nullable=True),
            sa.Column("full_name", sa.String(length=100), nullable=True),
            sa.Column("cpf", sa.String(length=11), nullable=True),
            sa.Column("whatsapp", sa.String(length=20), nullable=True),
            sa.Column("subscription_plan", sa.Enum("free", "basic", "premium", "enterprise", name="subscriptionplanenum"), nullable=True),
            sa.Column("subscription_status", sa.Enum("active", "inactive", "suspended", "cancelled", name="userstatusenum"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("subscription_start_date", sa.DateTime(), nullable=True),
            sa.Column("subscription_end_date", sa.DateTime(), nullable=True),
            sa.Column("last_access", sa.DateTime(), nullable=True),
            sa.Column("stripe_customer_id", sa.String(length=100), nullable=True),
            sa.Column("stripe_subscription_id", sa.String(length=100), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("trial_end_date", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
            sa.UniqueConstraint("stripe_customer_id"),
            sa.UniqueConstraint("stripe_subscription_id"),
        )

    if not inspector.has_table("conversations"):
        op.create_table(
            "conversations",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("audio_path", sa.String(length=255), nullable=True),
            sa.Column("transcript", sa.Text(), nullable=True),
            sa.Column("analysis", sa.JSON(), nullable=True),
            sa.Column("title", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("conversations"):
        op.drop_table("conversations")

    if inspector.has_table("users"):
        op.drop_table("users")
