import os
from collections.abc import Generator

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.rag.pipeline import ResolveAIPipeline


def get_pipeline(
    request: Request,
) -> ResolveAIPipeline:

    return request.app.state.pipeline


def get_db() -> Generator[
    Session,
    None,
    None,
]:
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def require_private_conversations() -> None:
    if os.getenv("PUBLIC_DEMO_MODE", "").strip().lower() == "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conversation access is disabled in public demo mode.",
        )
