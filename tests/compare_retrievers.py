from src.retrieval.retriever import (
    SemanticRetriever,
)

from src.retrieval.pgvector_retriever import (
    PgVectorRetriever,
)


def main():

    query = (
        "my refund still hasn't arrived"
    )

    top_k = 5

    numpy_retriever = (
        SemanticRetriever()
    )

    pgvector_retriever = (
        PgVectorRetriever()
    )

    numpy_results = (
        numpy_retriever.search(
            query,
            top_k=top_k
        )
    )

    pgvector_results = (
        pgvector_retriever.search(
            query,
            top_k=top_k
        )
    )

    print(
        "\nNUMPY RESULTS\n"
    )

    print(
        numpy_results[
            [
                "processed_instruction",
                "intent",
                "similarity",
            ]
        ]
    )

    print(
        "\nPGVECTOR RESULTS\n"
    )

    print(
        pgvector_results[
            [
                "processed_instruction",
                "intent",
                "similarity",
            ]
        ]
    )


if __name__ == "__main__":
    main()