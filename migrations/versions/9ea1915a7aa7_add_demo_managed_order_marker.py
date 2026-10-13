"""add demo managed order marker

Revision ID: 9ea1915a7aa7
Revises: 4a8f86efd979
Create Date: 2026-10-13 12:08:35.338146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ea1915a7aa7'
down_revision: Union[str, Sequence[str], None] = '4a8f86efd979'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "is_demo_managed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "orders",
        "is_demo_managed",
    )