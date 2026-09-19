from sqlalchemy import text

from src.db.database import engine


def check_connection():

    with engine.connect() as connection:

        version_result = connection.execute(
            text(
                "SELECT version();"
            )
        )

        print(
            "PostgreSQL connection successful."
        )

        print(
            version_result.scalar()
        )

        vector_result = connection.execute(
            text(
                """
                SELECT extversion
                FROM pg_extension
                WHERE extname = 'vector';
                """
            )
        )

        vector_version = (
            vector_result.scalar()
        )

        if vector_version is None:
            raise RuntimeError(
                "pgvector extension is not enabled."
            )

        print(
            "pgvector version:",
            vector_version
        )


if __name__ == "__main__":
    check_connection()