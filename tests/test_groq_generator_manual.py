from src.rag.prompt_builder import (
    PromptPayload,
)
from src.rag.providers.groq_provider import (
    GroqGenerator,
)


def main():

    prompt = PromptPayload(
        system_prompt=("You are a helpful customer-support assistant."),
        user_prompt=(
            "A customer says their refund "
            "has not arrived. Draft a short "
            "response asking for the "
            "necessary information without "
            "claiming that you checked "
            "their account."
        ),
    )

    generator = GroqGenerator()

    result = generator.generate(prompt)

    print("\nPROVIDER:", result.provider)

    print("MODEL:", result.model)

    print("\nGENERATED RESPONSE:\n")

    print(result.text)


if __name__ == "__main__":
    main()
