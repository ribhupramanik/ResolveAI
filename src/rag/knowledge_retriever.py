import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.retrieval.embeddings import (
    EmbeddingService,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_KNOWLEDGE_PATH = PROJECT_ROOT / "data" / "knowledge" / "knowledge_base.json"

DEFAULT_TOP_K = 2
DEFAULT_MIN_SIMILARITY = 0.35


@dataclass(frozen=True)
class KnowledgeMatch:
    topic: str
    content: str
    similarity: float


@dataclass
class VerifiedKnowledgeContext:
    context: str
    retrieved_count: int
    topics: list[str]
    max_similarity: float | None


class KnowledgeRetriever:
    def __init__(
        self,
        knowledge_path: Path = DEFAULT_KNOWLEDGE_PATH,
        embedding_service: EmbeddingService | None = None,
    ):

        self.knowledge_path = knowledge_path

        self.embedding_service = (
            embedding_service if embedding_service is not None else EmbeddingService()
        )

        self._items = self._load_knowledge()

        self._retrieval_texts = [
            self._build_retrieval_text(
                item["topic"],
                item["content"],
            )
            for item in self._items
        ]

        self._embeddings = np.asarray(
            self.embedding_service.encode(self._retrieval_texts),
            dtype=np.float32,
        )

        self._validate_embeddings()

    def _load_knowledge(self) -> list[dict]:

        if not self.knowledge_path.exists():
            raise FileNotFoundError(f"Knowledge base not found: {self.knowledge_path}")

        with self.knowledge_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Knowledge base must contain a JSON list.")

        if not data:
            raise ValueError("Knowledge base cannot be empty.")

        items = []

        for index, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValueError(f"Knowledge item {index} must be an object.")

            topic = item.get("topic")
            content = item.get("content")

            if not isinstance(topic, str) or not topic.strip():
                raise ValueError(f"Knowledge item {index} has an invalid topic.")

            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"Knowledge item {index} has invalid content.")

            items.append(
                {
                    "topic": topic.strip(),
                    "content": content.strip(),
                }
            )

        return items

    @staticmethod
    def _build_retrieval_text(
        topic: str,
        content: str,
    ) -> str:

        readable_topic = topic.replace(
            "_",
            " ",
        )

        return f"Topic: {readable_topic}. Verified knowledge: {content}"

    def _validate_embeddings(self) -> None:

        if self._embeddings.ndim != 2:
            raise ValueError("Knowledge embeddings must be a 2D matrix.")

        if len(self._embeddings) != len(self._items):
            raise ValueError("Knowledge item and embedding counts do not match.")

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = (DEFAULT_MIN_SIMILARITY),
    ) -> list[KnowledgeMatch]:

        if not isinstance(query, str):
            raise TypeError("Query must be a string.")

        if not query.strip():
            raise ValueError("Query cannot be empty.")

        if not isinstance(top_k, int):
            raise TypeError("top_k must be an integer.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        if not 0 <= min_similarity <= 1:
            raise ValueError("min_similarity must be between 0 and 1.")

        top_k = min(
            top_k,
            len(self._items),
        )

        query_embedding = np.asarray(
            self.embedding_service.encode([query])[0],
            dtype=np.float32,
        )

        similarities = self._embeddings @ query_embedding

        ranked_indices = np.argsort(similarities)[::-1]

        matches = []

        for index in ranked_indices[:top_k]:
            similarity = float(similarities[index])

            if similarity < min_similarity:
                continue

            item = self._items[index]

            matches.append(
                KnowledgeMatch(
                    topic=item["topic"],
                    content=item["content"],
                    similarity=similarity,
                )
            )

        return matches

    def build(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = (DEFAULT_MIN_SIMILARITY),
    ) -> VerifiedKnowledgeContext:

        matches = self.search(
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
        )

        if not matches:
            return VerifiedKnowledgeContext(
                context="",
                retrieved_count=0,
                topics=[],
                max_similarity=None,
            )

        sections = []

        for index, match in enumerate(
            matches,
            start=1,
        ):
            sections.append(
                f"Verified knowledge item "
                f"{index}\n"
                f"Topic: {match.topic}\n"
                f"Content: {match.content}"
            )

        return VerifiedKnowledgeContext(
            context="\n\n".join(sections),
            retrieved_count=len(matches),
            topics=[match.topic for match in matches],
            max_similarity=max(match.similarity for match in matches),
        )
