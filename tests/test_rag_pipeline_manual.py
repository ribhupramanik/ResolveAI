from src.rag.context_builder import (
    ContextBuilder,
)
from src.rag.prompt_builder import (
    PromptBuilder,
)
from src.rag.providers.groq_provider import (
    GroqGenerator,
)


def main():

    query = "my refund still hasn't arrived in my bank account"

    context_builder = ContextBuilder()

    prompt_builder = PromptBuilder()

    generator = GroqGenerator()

    retrieved_context = context_builder.build(query)

    prompt = prompt_builder.build(
        query,
        retrieved_context,
    )

    generated = generator.generate(prompt)

    print("\nCUSTOMER QUERY:\n")

    print(query)

    print("\nRETRIEVED EXAMPLES:", retrieved_context.retrieved_count)

    print("MAX SIMILARITY:", retrieved_context.max_similarity)

    print("\nMODEL:", generated.model)

    print("\nRESOLVEAI RESPONSE:\n")

    print(generated.text)


if __name__ == "__main__":
    main()
