"""Add finding confidence and dependency metadata

Revision ID: 002
Revises: 001
Create Date: 2026-05-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("confidence", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("package", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("current_version", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("fixed_version", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("findings", "fixed_version")
    op.drop_column("findings", "current_version")
    op.drop_column("findings", "package")
    op.drop_column("findings", "confidence")
