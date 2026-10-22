from src.retrieval import embeddings


def test_embedding_model_is_shared_between_services(monkeypatch):
    loaded_models = []

    def fake_loader(model_name):
        model = object()
        loaded_models.append(model_name)
        return model

    monkeypatch.setattr(
        embeddings,
        "SentenceTransformer",
        fake_loader,
    )

    first = embeddings.EmbeddingService(model_name="test-shared-model")
    second = embeddings.EmbeddingService(model_name="test-shared-model")

    assert first.model is second.model
    assert loaded_models == ["test-shared-model"]
