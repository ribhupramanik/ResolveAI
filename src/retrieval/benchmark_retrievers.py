from collections import Counter
from pathlib import Path
import statistics
import time

import numpy as np
import pandas as pd

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.db.database import engine
from src.db.models import SupportTicket
from src.retrieval.embeddings import EmbeddingService


EF_SEARCH_VALUES = [
    40,
    80,
    120,
    200,
]

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

VALIDATION_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "generic"
    / "validation.csv"
)

EMBEDDINGS_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "retrieval"
    / "corpus_embeddings.npy"
)

METADATA_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "retrieval"
    / "corpus_metadata.csv"
)


TOP_K = 5
SAMPLE_SIZE = 300
RANDOM_STATE = 42
WARMUP_QUERIES = 10


def summarize(values):

    return {
        "mean_ms": statistics.mean(
            values
        ),
        "median_ms": statistics.median(
            values
        ),
        "p95_ms": float(
            np.percentile(
                values,
                95
            )
        ),
    }


def load_validation_queries():

    validation_df = pd.read_csv(
        VALIDATION_PATH
    )

    if (
        "processed_instruction"
        not in validation_df.columns
    ):
        raise ValueError(
            "processed_instruction missing "
            "from validation data."
        )

    sample_size = min(
        SAMPLE_SIZE,
        len(validation_df)
    )

    sampled_df = (
        validation_df.sample(
            n=sample_size,
            random_state=RANDOM_STATE
        )
        .reset_index(
            drop=True
        )
    )

    return sampled_df


def load_numpy_corpus():

    embeddings = np.load(
        EMBEDDINGS_PATH
    )

    metadata = pd.read_csv(
        METADATA_PATH
    )

    if embeddings.ndim != 2:
        raise ValueError(
            "Corpus embeddings must "
            "be a 2D matrix."
        )

    if len(embeddings) != len(
        metadata
    ):
        raise ValueError(
            "Embedding and metadata "
            "row counts do not match."
        )

    return embeddings, metadata


def validate_database_alignment(
    metadata
):

    with Session(engine) as session:

        rows = (
            session.execute(
                select(
                    SupportTicket.id,
                    SupportTicket.processed_instruction,
                    SupportTicket.intent,
                    SupportTicket.response,
                )
                .order_by(
                    SupportTicket.id
                )
            )
            .all()
        )

    if len(rows) != len(metadata):
        raise ValueError(
            "Database row count does not "
            "match metadata row count."
        )

    database_ids = []

    for index, row in enumerate(rows):

        metadata_row = metadata.iloc[
            index
        ]

        if (
            row.processed_instruction
            != str(
                metadata_row[
                    "processed_instruction"
                ]
            )
        ):
            raise ValueError(
                "Database/metadata alignment "
                f"failed at row {index}."
            )

        if (
            row.intent
            != str(
                metadata_row["intent"]
            )
        ):
            raise ValueError(
                "Intent alignment failed "
                f"at row {index}."
            )

        if (
            row.response
            != str(
                metadata_row["response"]
            )
        ):
            raise ValueError(
                "Response alignment failed "
                f"at row {index}."
            )

        database_ids.append(
            row.id
        )

    print(
        "Database alignment validated."
    )

    return np.array(
        database_ids
    )


def make_content_key(
    instruction,
    intent,
):

    return (
        str(instruction),
        str(intent),
    )


def numpy_search(
    query_vector,
    corpus_embeddings,
    metadata,
    database_ids,
):

    similarities = (
        query_vector
        @ corpus_embeddings.T
    )

    top_indices = (
        np.argsort(
            similarities
        )[::-1][:TOP_K]
    )

    results = []

    for index in top_indices:

        results.append(
            {
                "id": int(
                    database_ids[index]
                ),
                "content_key":
                    make_content_key(
                        metadata.iloc[index][
                            "processed_instruction"
                        ],
                        metadata.iloc[index][
                            "intent"
                        ],
                    ),
                "similarity": float(
                    similarities[index]
                ),
            }
        )

    return results


def pgvector_search(
    query_vector,
    use_hnsw,
    ef_search=40,
):

    distance = (
        SupportTicket.embedding
        .cosine_distance(
            query_vector.tolist()
        )
        .label(
            "distance"
        )
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

        if use_hnsw:

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
                      ef_search
                  )
              },
            )

        else:

            session.execute(
                text(
                    "SET LOCAL "
                    "enable_indexscan = off"
                )
            )

            session.execute(
                text(
                    "SET LOCAL "
                    "enable_bitmapscan = off"
                )
            )

        rows = (
            session.execute(
                statement
            )
            .all()
        )

    results = []

    for row in rows:

        results.append(
            {
                "id": row.id,
                "content_key":
                    make_content_key(
                        row.processed_instruction,
                        row.intent,
                    ),
                "similarity":
                    1.0 - float(
                        row.distance
                    ),
            }
        )

    return results


def top1_id_agreement(
    reference,
    candidate,
):

    return (
        reference[0]["id"]
        == candidate[0]["id"]
    )


def top1_content_agreement(
    reference,
    candidate,
):

    return (
        reference[0]["content_key"]
        == candidate[0]["content_key"]
    )


def id_overlap(
    reference,
    candidate,
):

    reference_ids = {
        result["id"]
        for result in reference
    }

    candidate_ids = {
        result["id"]
        for result in candidate
    }

    return (
        len(
            reference_ids.intersection(
                candidate_ids
            )
        )
        / TOP_K
    )


def content_overlap(
    reference,
    candidate,
):

    reference_counter = Counter(
        result["content_key"]
        for result in reference
    )

    candidate_counter = Counter(
        result["content_key"]
        for result in candidate
    )

    common = (
        reference_counter
        & candidate_counter
    )

    return (
        sum(
            common.values()
        )
        / TOP_K
    )


def main():

    print(
        "Loading corpus..."
    )

    (
        corpus_embeddings,
        metadata,
    ) = load_numpy_corpus()

    database_ids = (
        validate_database_alignment(
            metadata
        )
    )

    print(
        "Loading validation queries..."
    )

    validation_df = (
        load_validation_queries()
    )

    queries = (
        validation_df[
            "processed_instruction"
        ]
        .astype(str)
        .tolist()
    )

    print(
        f"Validation queries: {len(queries)}"
    )

    print(
        "Generating query embeddings..."
    )

    embedding_service = (
        EmbeddingService()
    )

    query_embeddings = (
        embedding_service.encode(
            queries,
            batch_size=64
        )
    )

    print(
        "Query embeddings generated:",
        query_embeddings.shape
    )

    print(
        "Running warm-up..."
    )

    for query_vector in (
        query_embeddings[
            :WARMUP_QUERIES
        ]
    ):

        numpy_search(
            query_vector,
            corpus_embeddings,
            metadata,
            database_ids,
        )

        pgvector_search(
            query_vector,
            use_hnsw=False,
        )

        for ef_search in EF_SEARCH_VALUES:

            pgvector_search(
                query_vector,
                use_hnsw=True,
                ef_search=ef_search,
            )

    numpy_times = []
    exact_times = []

    #
    # NumPy vs pgvector exact
    #

    exact_id_top1 = []
    exact_content_top1 = []

    exact_id_top5 = []
    exact_content_top5 = []

    #
    # pgvector exact vs HNSW
    #

    hnsw_metrics = {}

    for ef_search in EF_SEARCH_VALUES:

        hnsw_metrics[ef_search] = {
            "times": [],
            "id_top1": [],
            "content_top1": [],
            "id_recall5": [],
            "content_recall5": [],
        }

    print(
        "Running benchmark..."
    )

    for query_vector in query_embeddings:

        #
        # NumPy exact
        #

        start = time.perf_counter()

        numpy_results = (
            numpy_search(
                query_vector,
                corpus_embeddings,
                metadata,
                database_ids,
            )
        )

        numpy_times.append(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

        #
        # pgvector exact
        #

        start = time.perf_counter()

        exact_results = (
            pgvector_search(
                query_vector,
                use_hnsw=False,
            )
        )

        exact_times.append(
            (
                time.perf_counter()
                - start
            )
            * 1000
        )

        #
        # NumPy vs pgvector exact
        #

        exact_id_top1.append(
            top1_id_agreement(
                numpy_results,
                exact_results,
            )
        )

        exact_content_top1.append(
            top1_content_agreement(
                numpy_results,
                exact_results,
            )
        )

        exact_id_top5.append(
            id_overlap(
                numpy_results,
                exact_results,
            )
        )

        exact_content_top5.append(
            content_overlap(
                numpy_results,
                exact_results,
            )
        )

    #
    # pgvector HNSW configurations
    #

    for ef_search in EF_SEARCH_VALUES:

        start = time.perf_counter()

        hnsw_results = (
            pgvector_search(
                query_vector,
                use_hnsw=True,
                ef_search=ef_search,
            )
        )

        elapsed_ms = (
            time.perf_counter()
            - start
        ) * 1000

        metrics = (
            hnsw_metrics[
                ef_search
            ]
        )

        metrics["times"].append(
            elapsed_ms
        )

        metrics["id_top1"].append(
            top1_id_agreement(
                exact_results,
                hnsw_results,
            )
        )

        metrics[
            "content_top1"
        ].append(
            top1_content_agreement(
                exact_results,
                hnsw_results,
            )
        )

        metrics[
            "id_recall5"
        ].append(
            id_overlap(
                exact_results,
                hnsw_results,
            )
        )

        metrics[
            "content_recall5"
        ].append(
            content_overlap(
                exact_results,
                hnsw_results,
            )
        )

    print(
        "\nNUMPY EXACT"
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
        "ID Top-1 agreement vs NumPy:",
        np.mean(
            exact_id_top1
        )
    )

    print(
        "Content Top-1 agreement vs NumPy:",
        np.mean(
            exact_content_top1
        )
    )

    print(
        "ID Top-5 overlap vs NumPy:",
        np.mean(
            exact_id_top5
        )
    )

    print(
        "Content Top-5 overlap vs NumPy:",
        np.mean(
            exact_content_top5
        )
    )

    
    for ef_search in EF_SEARCH_VALUES:

        metrics = (
            hnsw_metrics[
                ef_search
            ]
        )

        print(
            f"\nPGVECTOR HNSW "
            f"(ef_search={ef_search})"
        )

        print(
            summarize(
                metrics["times"]
            )
        )

        print(
            "ID Top-1 agreement vs PG exact:",
            np.mean(
                metrics[
                    "id_top1"
                ]
            )
        )

        print(
            "Content Top-1 agreement vs PG exact:",
            np.mean(
                metrics[
                    "content_top1"
                ]
            )
        )

        print(
            "ID Recall@5 vs PG exact:",
            np.mean(
                metrics[
                    "id_recall5"
                ]
            )
        )

        print(
            "Content Recall@5 vs PG exact:",
            np.mean(
                metrics[
                    "content_recall5"
                ]
            )
        )

if __name__ == "__main__":
    main()