from sqlalchemy import text

from src.db.database import SessionLocal, engine


def test_refund_checks_use_test_database():

    # Check the configured SQLAlchemy engine first.
    assert engine.url.database == "resolveai_test"

    # Verify the actual PostgreSQL connection.
    with SessionLocal() as db:

        database_name = db.execute(
            text("SELECT current_database()")
        ).scalar_one()

        assert database_name == "resolveai_test"