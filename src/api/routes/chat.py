from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
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

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


PipelineDependency = Annotated[
    ResolveAIPipeline,
    Depends(get_pipeline),
]


@router.post(
    "",
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
        retry_trigger_issues=(retry_trigger_issues),
        provider=result.provider,
        model=result.model,
    )

    return ChatResponse(
        message=result.text,
        metadata=metadata,
    )
