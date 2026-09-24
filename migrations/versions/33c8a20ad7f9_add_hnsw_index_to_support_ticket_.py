"""add hnsw index to support ticket embeddings

Revision ID: 33c8a20ad7f9
Revises: c836992dc17d
Create Date: 2026-09-24 11:38:55.346016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33c8a20ad7f9'
down_revision: Union[str, Sequence[str], None] = 'c836992dc17d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
     op.execute(
        """
        CREATE INDEX
        ix_support_tickets_embedding_hnsw
        ON support_tickets
        USING hnsw (
            embedding vector_cosine_ops
        )
        WITH (
            m = 16,
            ef_construction = 64
        );
        """
    )


def downgrade() -> None:
      op.execute(
        """
        DROP INDEX IF EXISTS
        ix_support_tickets_embedding_hnsw;
        """
    )
