from datetime import datetime, timezone
from pathlib import Path
import json

import numpy as np
import pandas as pd

from src.retrieval.embeddings import (
    EmbeddingService,
    MODEL_NAME,
)


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

ARTIFACT_DIR = (
    PROJECT_ROOT
    / "artifacts"
    / "retrieval"
)

EMBEDDINGS_PATH = (
    ARTIFACT_DIR
    / "corpus_embeddings.npy"
)

METADATA_PATH = (
    ARTIFACT_DIR
    / "corpus_metadata.csv"
)

MANIFEST_PATH = (
    ARTIFACT_DIR
    / "index_manifest.json"
)


REQUIRED_COLUMNS = {
    "processed_instruction",
    "intent",
    "response",
}


def build_index():

    print(
        "Loading retrieval corpus..."
    )

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    missing_columns = (
        REQUIRED_COLUMNS
        - set(train_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            f"{missing_columns}"
        )

    retrieval_metadata = (
        train_df[
            [
                "processed_instruction",
                "intent",
                "response",
            ]
        ]
        .reset_index(drop=True)
    )

    if (
        retrieval_metadata[
            "processed_instruction"
        ]
        .isna()
        .any()
    ):
        raise ValueError(
            "Missing retrieval text found."
        )

    print(
        "Corpus size:",
        len(retrieval_metadata)
    )

    embedding_service = (
        EmbeddingService()
    )

    print(
        "Generating embeddings..."
    )

    embeddings = (
        embedding_service.encode(
            retrieval_metadata[
                "processed_instruction"
            ].tolist(),
            batch_size=64,
        )
    )

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    np.save(
        EMBEDDINGS_PATH,
        embeddings,
    )

    retrieval_metadata.to_csv(
        METADATA_PATH,
        index=False,
    )

    manifest = {
        "embedding_model": MODEL_NAME,
        "embedding_dimension": int(
            embeddings.shape[1]
        ),
        "corpus_size": int(
            embeddings.shape[0]
        ),
        "normalized_embeddings": True,
        "source": (
            "data/processed/generic/train.csv"
        ),
        "created_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
    }

    with open(
        MANIFEST_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=4,
        )

    print(
        "Retrieval index created."
    )

    print(
        "Embeddings:",
        embeddings.shape
    )

    print(
        "Metadata rows:",
        len(retrieval_metadata)
    )


if __name__ == "__main__":
    build_index()