from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=2)
def load_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class EmbeddingService:
    def __init__(
        self,
        model_name: str = MODEL_NAME,
    ):
        self.model = load_model(model_name)

    def encode(
        self,
        texts,
        batch_size: int = 64,
    ):
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
