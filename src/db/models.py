from datetime import datetime

from pgvector.sqlalchemy import Vector

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from src.db.database import Base


class SupportTicket(Base):

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    instruction: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    processed_instruction: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False
        )
    )

    intent: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    response: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    source_split: Mapped[str] = (
        mapped_column(
            String(30),
            nullable=False,
            default="train"
        )
    )

    embedding: Mapped[list] = mapped_column(
        Vector(384),
        nullable=False
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(timezone=True),
            server_default=func.now()
        )
    )