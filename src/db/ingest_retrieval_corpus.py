from pathlib import Path

import numpy as np
import pandas as pd

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from src.db.database import engine
from src.db.models import SupportTicket


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

TRAIN_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "generic"
    / "train.csv"
)

METADATA_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "retrieval"
    / "corpus_metadata.csv"
)

EMBEDDINGS_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "retrieval"
    / "corpus_embeddings.npy"
)

EXPECTED_EMBEDDING_DIM = 384
BATCH_SIZE = 500


def load_and_validate_data():

    print("Loading training data...")

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    metadata_df = pd.read_csv(
        METADATA_PATH
    )

    embeddings = np.load(
        EMBEDDINGS_PATH
    )

    required_train_columns = {
        "instruction",
        "processed_instruction",
        "intent",
        "response",
    }

    required_metadata_columns = {
        "processed_instruction",
        "intent",
        "response",
    }

    missing_train_columns = (
        required_train_columns
        - set(train_df.columns)
    )

    if missing_train_columns:
        raise ValueError(
            "Training data is missing columns: "
            f"{sorted(missing_train_columns)}"
        )

    missing_metadata_columns = (
        required_metadata_columns
        - set(metadata_df.columns)
    )

    if missing_metadata_columns:
        raise ValueError(
            "Retrieval metadata is missing columns: "
            f"{sorted(missing_metadata_columns)}"
        )

    if embeddings.ndim != 2:
        raise ValueError(
            "Embeddings must be a 2D matrix."
        )

    if (
        embeddings.shape[1]
        != EXPECTED_EMBEDDING_DIM
    ):
        raise ValueError(
            "Unexpected embedding dimension: "
            f"{embeddings.shape[1]}"
        )

    row_counts = {
        len(train_df),
        len(metadata_df),
        len(embeddings),
    }

    if len(row_counts) != 1:
        raise ValueError(
            "Training data, metadata and "
            "embeddings have different row counts."
        )

    required_columns = [
        "instruction",
        "processed_instruction",
        "intent",
        "response",
    ]

    if (
        train_df[required_columns]
        .isnull()
        .any()
        .any()
    ):
        raise ValueError(
            "Training data contains missing "
            "values in required columns."
        )

    print(
        "Validating metadata alignment..."
    )

    alignment_columns = [
        "processed_instruction",
        "intent",
        "response",
    ]

    for column in alignment_columns:

        train_values = (
            train_df[column]
            .astype(str)
            .reset_index(drop=True)
        )

        metadata_values = (
            metadata_df[column]
            .astype(str)
            .reset_index(drop=True)
        )

        if not train_values.equals(
            metadata_values
        ):
            raise ValueError(
                "Retrieval metadata is not "
                f"aligned with train.csv "
                f"for column '{column}'."
            )

    print(
        "Data validation passed."
    )

    print(
        f"Rows: {len(train_df)}"
    )

    print(
        f"Embeddings: {embeddings.shape}"
    )

    return train_df, embeddings


def ingest(
    replace_existing=False
):

    train_df, embeddings = (
        load_and_validate_data()
    )

    with Session(engine) as session:

        existing_count = (
            session.scalar(
                select(
                    func.count(
                        SupportTicket.id
                    )
                )
            )
            or 0
        )

        if existing_count > 0:

            if not replace_existing:
                raise RuntimeError(
                    "support_tickets already "
                    f"contains {existing_count} rows. "
                    "Ingestion stopped to prevent "
                    "duplicate records."
                )

            print(
                "Removing existing records..."
            )

            session.execute(
                delete(
                    SupportTicket
                )
            )

            session.commit()

        total_rows = len(train_df)

        print(
            "Starting database ingestion..."
        )

        for start in range(
            0,
            total_rows,
            BATCH_SIZE
        ):

            end = min(
                start + BATCH_SIZE,
                total_rows
            )

            batch = []

            for index in range(
                start,
                end
            ):

                row = train_df.iloc[
                    index
                ]

                batch.append(
                    SupportTicket(
                        instruction=str(
                            row[
                                "instruction"
                            ]
                        ),
                        processed_instruction=str(
                            row[
                                "processed_instruction"
                            ]
                        ),
                        intent=str(
                            row[
                                "intent"
                            ]
                        ),
                        response=str(
                            row[
                                "response"
                            ]
                        ),
                        source_split="train",
                        embedding=embeddings[
                            index
                        ].tolist(),
                    )
                )

            session.add_all(
                batch
            )

            session.commit()

            print(
                f"Inserted {end}/{total_rows}"
            )

        final_count = (
            session.scalar(
                select(
                    func.count(
                        SupportTicket.id
                    )
                )
            )
            or 0
        )

        if final_count != total_rows:
            raise RuntimeError(
                "Database row count does not "
                "match corpus row count. "
                f"Expected {total_rows}, "
                f"found {final_count}."
            )

        print(
            "Ingestion completed successfully."
        )

        print(
            f"Database rows: {final_count}"
        )


if __name__ == "__main__":
    ingest()