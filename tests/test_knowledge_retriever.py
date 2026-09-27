import json

import numpy as np
import pytest

from src.rag.knowledge_retriever import (
    KnowledgeRetriever,
)


class FakeEmbeddingService:
    def encode(
        self,
        texts,
    ):

        embeddings = []

        for text in texts:
            text = text.lower()

            if "payment method" in text or "cards" in text:
                vector = [
                    1.0,
                    0.0,
                    0.0,
                ]

            elif "refund" in text:
                vector = [
                    0.0,
                    1.0,
                    0.0,
                ]

            else:
                vector = [
                    0.0,
                    0.0,
                    1.0,
                ]

            embeddings.append(vector)

        return np.asarray(
            embeddings,
            dtype=np.float32,
        )


@pytest.fixture
def knowledge_path(
    tmp_path,
):

    data = [
        {
            "topic": "payment_methods",
            "content": (
                "No verified information about supported payment methods is available."
            ),
        },
        {
            "topic": "refund_timeline",
            "content": ("No verified refund timeline is available."),
        },
    ]

    path = tmp_path / "knowledge_base.json"

    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    return path


@pytest.fixture
def retriever(
    knowledge_path,
):

    return KnowledgeRetriever(
        knowledge_path=knowledge_path,
        embedding_service=(FakeEmbeddingService()),
    )


def test_retrieves_payment_knowledge(
    retriever,
):

    matches = retriever.search("what cards can I use?")

    assert len(matches) >= 1

    assert matches[0].topic == "payment_methods"


def test_retrieves_refund_knowledge(
    retriever,
):

    matches = retriever.search("how long does my refund take?")

    assert len(matches) >= 1

    assert matches[0].topic == "refund_timeline"


def test_build_returns_context(
    retriever,
):

    result = retriever.build("what payment methods are accepted?")

    assert result.retrieved_count >= 1

    assert "payment_methods" in result.topics

    assert "Verified knowledge item" in result.context


def test_empty_query_raises_error(
    retriever,
):

    with pytest.raises(ValueError):
        retriever.search("   ")


def test_invalid_top_k_raises_error(
    retriever,
):

    with pytest.raises(ValueError):
        retriever.search(
            "where is my refund?",
            top_k=0,
        )


def test_high_threshold_can_return_empty(
    retriever,
):

    matches = retriever.search(
        "something unrelated",
        min_similarity=0.99,
    )

    assert matches == []
