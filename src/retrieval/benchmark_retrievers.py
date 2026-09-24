import statistics
import time

import numpy as np

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.db.database import engine
from src.db.models import SupportTicket
from src.retrieval.embeddings import EmbeddingService
from src.retrieval.retriever import SemanticRetriever


TEST_QUERIES = [
    "my refund still hasn't arrived",
    "where is my order",
    "I forgot my password",
    "how can I delete my account",
    "what payment methods do you accept",
    "I want to change my shipping address",
    "how long does delivery take",
    "I need a copy of my invoice",
]


TOP_K = 5
REPEATS = 10


def percentile_95(values):

    return float(
        np.percentile(
            values,
            95
        )
    )


def summarize(
    values
):

    return {
        "mean_ms":
            statistics.mean(values),

        "median_ms":
            statistics.median(values),

        "p95_ms":
            percentile_95(values),
    }


def pgvector_search(
    query_vector,
    use_hnsw=True
):

    distance = (
        SupportTicket.embedding
        .cosine_distance(
            query_vector
        )
        .label("distance")
    )

    statement = (
        select(
            SupportTicket.id,
            SupportTicket.processed_instruction,
            SupportTicket.intent,
            distance,
        )
        .order_by(
            distance
        )
        .limit(
            TOP_K
        )
    )

    with Session(engine) as session:

        if not use_hnsw:

            session.execute(
                text(
                    "SET LOCAL enable_indexscan = off"
                )
            )

        rows = (
            session.execute(
                statement
            )
            .all()
        )

    return rows


def main():

    embedding_service = (
        EmbeddingService()
    )

    numpy_retriever = (
        SemanticRetriever()
    )

    numpy_times = []
    exact_times = []
    hnsw_times = []

    exact_top5_overlap = []
    hnsw_top5_overlap = []

    for query in TEST_QUERIES:

        query_vector = (
            embedding_service.encode(
                [query]
            )[0]
            .tolist()
        )

        numpy_results = (
            numpy_retriever.search(
                query,
                top_k=TOP_K
            )
        )

        numpy_reference = (
            numpy_results[
                "processed_instruction"
            ].tolist()
        )

        for _ in range(REPEATS):

            start = (
                time.perf_counter()
            )

            numpy_retriever.search(
                query,
                top_k=TOP_K
            )

            numpy_times.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

            start = (
                time.perf_counter()
            )

            exact_results = (
                pgvector_search(
                    query_vector,
                    use_hnsw=False
                )
            )

            exact_times.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

            start = (
                time.perf_counter()
            )

            hnsw_results = (
                pgvector_search(
                    query_vector,
                    use_hnsw=True
                )
            )

            hnsw_times.append(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )

        exact_names = [
            row.processed_instruction
            for row in exact_results
        ]

        hnsw_names = [
            row.processed_instruction
            for row in hnsw_results
        ]

        reference_set = set(
            numpy_reference
        )

        exact_overlap = (
            len(
                reference_set.intersection(
                    exact_names
                )
            )
            / TOP_K
        )

        hnsw_overlap = (
            len(
                reference_set.intersection(
                    hnsw_names
                )
            )
            / TOP_K
        )

        exact_top5_overlap.append(
            exact_overlap
        )

        hnsw_top5_overlap.append(
            hnsw_overlap
        )

    print(
        "\nNUMPY"
    )

    print(
        summarize(
            numpy_times
        )
    )

    print(
        "\nPGVECTOR EXACT"
    )

    print(
        summarize(
            exact_times
        )
    )

    print(
        "Top-5 agreement:",
        statistics.mean(
            exact_top5_overlap
        )
    )

    print(
        "\nPGVECTOR HNSW"
    )

    print(
        summarize(
            hnsw_times
        )
    )

    print(
        "Top-5 agreement:",
        statistics.mean(
            hnsw_top5_overlap
        )
    )


if __name__ == "__main__":
    main()