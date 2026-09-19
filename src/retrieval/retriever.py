from pathlib import Path

import numpy as np
import pandas as pd

from src.retrieval.embeddings import (
    EmbeddingService
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
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


class SemanticRetriever:

    def __init__(self):

        self.embedding_service = (
            EmbeddingService()
        )

        self.embeddings = np.load(
            EMBEDDINGS_PATH
        )

        self.metadata = pd.read_csv(
            METADATA_PATH
        )

        # Validate embedding matrix shape
        if self.embeddings.ndim != 2:
            raise ValueError(
                "Corpus embeddings must be "
                "a 2D matrix."
            )

        # Ensure embedding rows correspond
        # exactly to metadata rows
        if (
            len(self.embeddings)
            != len(self.metadata)
        ):
            raise ValueError(
                "Embedding and metadata "
                "row counts do not match."
            )

    def search(
        self,
        query: str,
        top_k: int = 5
    ):

        if not query.strip():
            raise ValueError(
                "Query cannot be empty."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        # Prevent asking for more results
        # than exist in the corpus
        if top_k > len(self.metadata):
            top_k = len(self.metadata)

        query_embedding = (
            self.embedding_service.encode(
                [query]
            )
        )

        similarities = (
            query_embedding
            @ self.embeddings.T
        )[0]

        top_indices = (
            np.argsort(
                similarities
            )[::-1][:top_k]
        )

        results = (
            self.metadata
            .iloc[top_indices]
            .copy()
        )

        results["similarity"] = (
            similarities[
                top_indices
            ]
        )

        return results.reset_index(
            drop=True
        )