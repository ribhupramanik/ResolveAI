import pandas as pd

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy import text
from src.db.database import SessionLocal
from src.db.models import SupportTicket
from src.retrieval.embeddings import (
    EmbeddingService,
)


EXPECTED_EMBEDDING_DIM = 384
HNSW_EF_SEARCH = 120


class PgVectorRetriever:

    def __init__(self):

        self.embedding_service = (
            EmbeddingService()
        )

        with SessionLocal() as session:

            self.corpus_size = (
                session.scalar(
                    select(
                        func.count(
                            SupportTicket.id
                        )
                    )
                )
                or 0
            )

        if self.corpus_size == 0:
            raise RuntimeError(
                "support_tickets is empty."
            )

    def search(
        self,
        query: str,
        top_k: int = 5
    ) -> pd.DataFrame:

        if not isinstance(query, str):
            raise TypeError(
                "Query must be a string."
            )

        if not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        top_k = min(
            top_k,
            self.corpus_size
        )

        query_embedding = (
            self.embedding_service.encode(
                [query]
            )[0]
        )

        if (
            query_embedding.ndim != 1
            or len(query_embedding)
            != EXPECTED_EMBEDDING_DIM
        ):
            raise ValueError(
                "Query embedding must be a "
                "384-dimensional vector."
            )

        query_vector = (
            query_embedding.tolist()
        )

        cosine_distance = (
            SupportTicket.embedding
            .cosine_distance(
                query_vector
            )
            .label(
                "distance"
            )
        )

        statement = (
            select(
                SupportTicket.id,
                SupportTicket.instruction,
                SupportTicket.processed_instruction,
                SupportTicket.intent,
                SupportTicket.response,
                SupportTicket.source_split,
                cosine_distance,
            )
            .order_by(
                cosine_distance
            )
            .limit(
                top_k
            )
        )

        with SessionLocal() as session:

            session.execute(
                text(
                    """
                    SELECT set_config(
                        'hnsw.ef_search',
                        :value,
                        true
                    )
                    """
                ),
                {
                    "value": str(
                        HNSW_EF_SEARCH
                    )
                },
            )

            rows = (
                session.execute(
                    statement
                )
                .all()
            )

        results = []

        for row in rows:

            distance = float(
                row.distance
            )

            results.append(
                {
                    "id": row.id,
                    "instruction": row.instruction,
                    "processed_instruction":
                        row.processed_instruction,
                    "intent": row.intent,
                    "response": row.response,
                    "source_split":
                        row.source_split,
                    "similarity":
                        1.0 - distance,
                }
            )

        return pd.DataFrame(
            results
        )