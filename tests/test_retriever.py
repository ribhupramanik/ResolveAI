import pytest

from src.retrieval import SemanticRetriever


@pytest.fixture(scope="module")
def retriever():
    return SemanticRetriever()


def test_retriever_returns_requested_results(
    retriever
):
    results = retriever.search(
        "where is my refund",
        top_k=3
    )

    assert len(results) == 3

    assert "processed_instruction" in results.columns
    assert "intent" in results.columns
    assert "similarity" in results.columns

    assert (
        results["similarity"]
        .is_monotonic_decreasing
    )


def test_empty_query_raises_error(
    retriever
):
    with pytest.raises(ValueError):
        retriever.search(
            "",
            top_k=5
        )


def test_invalid_top_k_raises_error(
    retriever
):
    with pytest.raises(ValueError):
        retriever.search(
            "where is my refund",
            top_k=0
        )

def test_similarity_values_are_valid(
    retriever
):
    results = retriever.search(
        "where is my refund",
        top_k=5
    )

    assert (
        results["similarity"]
        <= 1.0 + 1e-6
    ).all()

    assert (
        results["similarity"]
        >= -1.0 - 1e-6
    ).all()

def test_top_k_larger_than_corpus(
    retriever
):
    results = retriever.search(
        "where is my refund",
        top_k=50000
    )

    assert len(results) == len(
        retriever.metadata
    )