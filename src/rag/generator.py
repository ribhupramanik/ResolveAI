from dataclasses import dataclass
from typing import Protocol

from src.rag.prompt_builder import (
    PromptPayload,
)


@dataclass
class GeneratedResponse:
    text: str
    model: str
    provider: str


class Generator(Protocol):

    def generate(
        self,
        prompt: PromptPayload,
    ) -> GeneratedResponse:
        ...