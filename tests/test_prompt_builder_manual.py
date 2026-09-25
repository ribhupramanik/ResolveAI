from src.rag.context_builder import ContextBuilder
from src.rag.prompt_builder import PromptBuilder


def main():

    query = "my refund still hasn't arrived in my bank account"

    context_builder = ContextBuilder()
    prompt_builder = PromptBuilder()
    retrieved_context = context_builder.build(query)

    prompt = prompt_builder.build(query, retrieved_context)
    print("\nSYSTEM PROMPT:\n")

    print(prompt.system_prompt)

    print("\nUSER PROMPT:\n")

    print(prompt.user_prompt)


if __name__ == "__main__":
    main()
