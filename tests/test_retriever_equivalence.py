import numpy as np
import pytest

from src.retrieval.retriever import (
    SemanticRetriever,
)

from src.retrieval.pgvector_retriever import (
    PgVectorRetriever,
)


@pytest.fixture(scope="module")
def numpy_retriever():
    return SemanticRetriever()


@pytest.fixture(scope="module")
def pgvector_retriever():
    return PgVectorRetriever()


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


@pytest.mark.parametrize(
    "query",
    TEST_QUERIES,
)
def test_retrievers_are_equivalent(
    query,
    numpy_retriever,
    pgvector_retriever,
):

    top_k = 5

    numpy_results = (
        numpy_retriever.search(
            query,
            top_k=top_k,
        )
    )

    pgvector_results = (
        pgvector_retriever.search(
            query,
            top_k=top_k,
        )
    )

    assert len(numpy_results) == top_k
    assert len(pgvector_results) == top_k

    assert (
        numpy_results[
            "processed_instruction"
        ].tolist()
        ==
        pgvector_results[
            "processed_instruction"
        ].tolist()
    )

    assert (
        numpy_results[
            "intent"
        ].tolist()
        ==
        pgvector_results[
            "intent"
        ].tolist()
    )

    assert np.allclose(
        numpy_results[
            "similarity"
        ].to_numpy(),
        pgvector_results[
            "similarity"
        ].to_numpy(),
        atol=1e-6,
    )