
from collections.abc import Generator

from fastapi import Request
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
