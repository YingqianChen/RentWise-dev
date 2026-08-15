"""Add notes to investigation items.

Revision ID: 20260816_0016
Revises: 20260813_0015
Create Date: 2026-08-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260816_0016"
down_revision: Union[str, None] = "20260813_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investigation_items", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("investigation_items", "note")
