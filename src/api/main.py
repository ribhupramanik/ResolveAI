from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)

from src.api.dependencies import (
    get_pipeline,
)
from src.api.schemas.chat import (
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    ValidationIssueResponse,
)
from src.rag.pipeline import (
    ResolveAIPipeline,
)
from src.rag.providers.groq_provider import (
    GroqGenerator,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    app.state.pipeline = ResolveAIPipeline(generator=GroqGenerator())

    yield


app = FastAPI(
    title="ResolveAI API",
    description=("API for the ResolveAI customer-support intelligence platform."),
    version="0.1.0",
    lifespan=lifespan,
)


PipelineDependency = Annotated[
    ResolveAIPipeline,
    Depends(get_pipeline),
]


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "service": "ResolveAI",
    }


@app.post(
    "/api/v1/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    pipeline: PipelineDependency,
) -> ChatResponse:

    try:
        result = pipeline.run(request.message)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=("ResolveAI could not process the request."),
        ) from exc

    retry_trigger_issues = [
        ValidationIssueResponse(
            code=issue.code,
            message=issue.message,
            matched_text=issue.matched_text,
        )
        for issue in result.validation_issues
    ]

    metadata = ChatMetadata(
        retrieved_count=(result.retrieved_count),
        verified_knowledge_count=(result.verified_knowledge_count),
        verified_knowledge_topics=(result.verified_knowledge_topics),
        system_capability_count=(result.system_capability_count),
        system_capabilities=(result.system_capabilities),
        attempts=result.attempts,
        used_fallback=result.used_fallback,
        retry_trigger_issues=retry_trigger_issues,
        provider=result.provider,
        model=result.model,
    )

    return ChatResponse(
        message=result.text,
        metadata=metadata,
    )
