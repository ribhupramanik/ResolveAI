from src.retrieval import (
    SemanticRetriever
)


retriever = SemanticRetriever()

results = retriever.search(
    "my refund still hasn't arrived",
    top_k=5
)

print(
    results[
        [
            "processed_instruction",
            "intent",
            "similarity"
        ]
    ]
)