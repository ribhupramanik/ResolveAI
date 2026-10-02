from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
        description="Customer message sent to ResolveAI.",
    )


class ValidationIssueResponse(BaseModel):
    code: str
    message: str
    matched_text: str


class ChatMetadata(BaseModel):
    retrieved_count: int

    verified_knowledge_count: int
    verified_knowledge_topics: list[str]

    system_capability_count: int
    system_capabilities: list[str]

    tool_used: bool
    tool_name: str | None = None
    tool_success: bool | None = None

    attempts: int
    used_fallback: bool

    retry_trigger_issues: list[ValidationIssueResponse]

    provider: str | None
    model: str | None


class ChatResponse(BaseModel):
    message: str
    metadata: ChatMetadata
