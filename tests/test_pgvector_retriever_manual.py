from src.retrieval.pgvector_retriever import (
    PgVectorRetriever,
)


def main():

    retriever = PgVectorRetriever()

    query = (
        "my refund still hasn't arrived"
    )

    results = retriever.search(
        query,
        top_k=5
    )

    print(
        results[
            [
                "instruction",
                "intent",
                "similarity",
            ]
        ]
    )


if __name__ == "__main__":
    main()