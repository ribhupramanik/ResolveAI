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