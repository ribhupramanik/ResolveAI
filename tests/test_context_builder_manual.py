from src.rag.context_builder import (
    ContextBuilder,
)


def main():

    builder = ContextBuilder()

    query = (
        "my refund still hasn't "
        "arrived in my bank account"
    )

    result = builder.build(
        query
    )

    print(
        "\nQUERY:\n"
    )

    print(
        query
    )

    print(
        "\nRETRIEVED COUNT:",
        result.retrieved_count
    )

    print(
        "MAX SIMILARITY:",
        result.max_similarity
    )

    print(
        "MIN SIMILARITY:",
        result.min_similarity
    )

    print(
        "\nRAG CONTEXT:\n"
    )

    print(
        result.context
    )


if __name__ == "__main__":
    main()