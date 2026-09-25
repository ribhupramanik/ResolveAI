import os

from dotenv import load_dotenv
from groq import Groq

from src.rag.generator import GeneratedResponse
from src.rag.prompt_builder import PromptPayload

load_dotenv()

DEFAULT_MODEL = "openai/gpt-oss-20b"


class GroqGenerator:
    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        self.model = model

        self.client = Groq(api_key=api_key, timeout=30.0)

    def generate(self, prompt: PromptPayload) -> GeneratedResponse:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": prompt.system_prompt,
                },
                {"role": "user", "content": prompt.user_prompt},
            ],
            temperature=0.2,
            max_completion_tokens=512,
            include_reasoning=False,
        )

        content = completion.choices[0].message.content

        if not content:
            raise RuntimeError("Groq returned an empty response.")

        return GeneratedResponse(
            text=content.strip(),
            model=self.model,
            provider="groq",
        )
