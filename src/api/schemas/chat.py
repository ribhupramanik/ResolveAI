from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="Customer message sent to ResolveAI.",
    )


class ChatResponse(BaseModel):
    message: str
