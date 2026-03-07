"""add free analyses remaining to users

Revision ID: c2f8d9e1a4b7
Revises: 9f83bff4d6a1
Create Date: 2026-03-07 18:25:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c2f8d9e1a4b7"
down_revision: Union[str, Sequence[str], None] = "9f83bff4d6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "free_analyses_remaining" not in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "free_analyses_remaining",
                    sa.Integer(),
                    nullable=False,
                    server_default="2",
                )
            )

    # Backfill based on historical number of conversations per user.
    op.execute(
        """
        UPDATE users
        SET free_analyses_remaining = CASE
            WHEN (
                SELECT COUNT(1)
                FROM conversations c
                WHERE c.user_id = users.id
            ) >= 2 THEN 0
            ELSE 2 - (
                SELECT COUNT(1)
                FROM conversations c
                WHERE c.user_id = users.id
            )
        END
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "free_analyses_remaining" in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("free_analyses_remaining")
