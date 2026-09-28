from src.rag.pipeline import (
    ResolveAIPipeline,
)
from src.rag.providers.groq_provider import (
    GroqGenerator,
)


def main():

    query = "my refund still hasn't arrived in my bank account"

    pipeline = ResolveAIPipeline(generator=GroqGenerator())

    result = pipeline.run(query)

    print("\nCUSTOMER QUERY:\n")

    print(query)

    print("\nRESOLVEAI RESPONSE:\n")

    print(result.text)

    print("\nATTEMPTS:", result.attempts)

    print("USED FALLBACK:", result.used_fallback)

    print("RETRIEVED EXAMPLES:", result.retrieved_count)

    print("VERIFIED KNOWLEDGE COUNT:", result.verified_knowledge_count)

    print("VERIFIED KNOWLEDGE TOPICS:", result.verified_knowledge_topics)

    print("SYSTEM CAPABILITY COUNT:",result.system_capability_count,)

    print("SYSTEM CAPABILITIES:",result.system_capabilities)

    print("PROVIDER:", result.provider)

    print("MODEL:", result.model)

    print("\nVALIDATION ISSUES:")

    if not result.validation_issues:
        print("None")

    else:
        for issue in result.validation_issues:
            print(
                "-",
                issue.code,
                "->",
                issue.matched_text,
            )


if __name__ == "__main__":
    main()
