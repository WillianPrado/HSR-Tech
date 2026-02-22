"""conversation uuid model update

Revision ID: 6d5405646c76
Revises: 0001_initial_schema
Create Date: 2026-02-22 17:59:31.921318
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d5405646c76'
down_revision: Union[str, Sequence[str], None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("conversations", recreate="always") as batch_op:
        batch_op.alter_column(
            "id",
            existing_type=sa.NUMERIC(),
            type_=sa.UUID(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("conversations", recreate="always") as batch_op:
        batch_op.alter_column(
            "id",
            existing_type=sa.UUID(),
            type_=sa.NUMERIC(),
            existing_nullable=False,
        )
