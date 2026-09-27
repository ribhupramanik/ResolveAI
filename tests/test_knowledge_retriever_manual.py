from src.rag.knowledge_retriever import (
    KnowledgeRetriever,
)

QUERIES = [
    "What payment methods can I use?",
    "My refund still hasn't reached my bank account.",
    "Where is my order right now?",
    "I forgot my account password.",
    "I want to permanently delete my account.",
    "I need to change my shipping address.",
    "How long will delivery take?",
    "Can you send me my invoice?",
    "I want to cancel my order.",
    "There is a problem with my payment.",
    "I need to speak with a human agent.",
    "How do I create a new account?",
]


def main():

    retriever = KnowledgeRetriever()

    for query in QUERIES:
        print("\n" + "=" * 80)

        print(f"QUERY: {query}")

        result = retriever.build(query)

        print(
            "RETRIEVED COUNT:",
            result.retrieved_count,
        )

        print(
            "TOPICS:",
            result.topics,
        )

        print(
            "MAX SIMILARITY:",
            result.max_similarity,
        )

        if result.context:
            print("\nVERIFIED KNOWLEDGE:\n")

            print(result.context)

        else:
            print("\nNo verified knowledge retrieved.")


if __name__ == "__main__":
    main()
