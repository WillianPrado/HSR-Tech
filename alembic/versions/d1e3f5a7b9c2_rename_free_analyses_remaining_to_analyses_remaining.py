"""rename free_analyses_remaining to analyses_remaining

Revision ID: d1e3f5a7b9c2
Revises: c2f8d9e1a4b7
Create Date: 2026-03-14 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "d1e3f5a7b9c2"
down_revision: Union[str, Sequence[str], None] = "c2f8d9e1a4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "free_analyses_remaining" in columns and "analyses_remaining" not in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column("free_analyses_remaining", new_column_name="analyses_remaining")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("users")}

    if "analyses_remaining" in columns and "free_analyses_remaining" not in columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column("analyses_remaining", new_column_name="free_analyses_remaining")
