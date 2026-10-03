from datetime import (
    datetime,
    timezone,
)
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.dependencies import (
    get_db,
    get_pipeline,
)
from src.api.schemas.chat import (
    ChatMetadata,
    ValidationIssueResponse,
)
from src.api.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
)
from src.api.schemas.message import (
    ConversationMessageResponse,
    MessageCreate,
    MessageResponse,
)
from src.db.models import (
    Conversation,
    Message,
)
from src.rag.conversation import (
    ConversationTurn,
)
from src.rag.pipeline import (
    ResolveAIPipeline,
)
from src.services.pending_action_confirmation import (
    resolve_pending_action_response,
)
from src.services.pending_action_integration import (
    maybe_create_pending_cancellation,
)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)

PipelineDependency = Annotated[
    ResolveAIPipeline,
    Depends(get_pipeline),
]

DatabaseDependency = Annotated[
    Session,
    Depends(get_db),
]


def build_conversation_title(
    message: str,
    max_length: int = 50,
) -> str:
    clean_message = " ".join(message.split())

    if len(clean_message) <= max_length:
        return clean_message

    return clean_message[:max_length].rstrip() + "..."


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreate,
    db: DatabaseDependency,
) -> Conversation:

    title = (
        payload.title.strip()
        if payload.title and payload.title.strip()
        else "New conversation"
    )

    conversation = Conversation(title=title)

    db.add(conversation)

    db.commit()

    db.refresh(conversation)

    return conversation


@router.get(
    "",
    response_model=list[ConversationResponse],
)
def list_conversations(
    db: DatabaseDependency,
) -> list[Conversation]:

    statement = select(Conversation).order_by(
        Conversation.updated_at.desc(),
        Conversation.id.desc(),
    )

    conversations = db.scalars(statement).all()

    return list(conversations)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def get_conversation(
    conversation_id: int,
    db: DatabaseDependency,
) -> Conversation:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def list_messages(
    conversation_id: int,
    db: DatabaseDependency,
) -> list[Message]:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(
            Message.created_at.asc(),
            Message.id.asc(),
        )
    )

    messages = db.scalars(statement).all()

    return list(messages)


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: DatabaseDependency,
    pipeline: PipelineDependency,
) -> ConversationMessageResponse:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    customer_text = payload.message.strip()

    history_statement = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id.desc())
        .limit(12)
    )

    recent_messages = list(db.scalars(history_statement).all())

    recent_messages.reverse()

    if conversation.title == "New conversation" and not recent_messages:
        conversation.title = build_conversation_title(customer_text)

    conversation_history = [
        ConversationTurn(
            role=item.role,
            content=item.content,
        )
        for item in recent_messages
    ]

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=customer_text,
    )

    db.add(user_message)

    try:
        pending_decision = resolve_pending_action_response(
            db=db,
            conversation_id=conversation.id,
            customer_text=customer_text,
        )

        if pending_decision.handled:
            action = pending_decision.action

            if action is None:
                raise RuntimeError("Handled pending action has no action.")

            if pending_decision.decision == "confirmed":
                assistant_text = (
                    f"Cancellation of "
                    f"{action.target_identifier} "
                    f"has been confirmed. "
                    f"No cancellation has been performed yet."
                )

            elif pending_decision.decision == "rejected":
                assistant_text = (
                    f"The pending cancellation request for "
                    f"{action.target_identifier} "
                    f"has been rejected. "
                    f"No cancellation has been performed."
                )

            else:
                raise RuntimeError("Unknown pending action decision.")

            metadata_data = {
                "retrieved_count": 0,
                "verified_knowledge_count": 0,
                "verified_knowledge_topics": [],
                "system_capability_count": 0,
                "system_capabilities": [],
                "tool_used": False,
                "tool_name": None,
                "tool_success": None,
                "attempts": 0,
                "used_fallback": False,
                "retry_trigger_issues": [],
                "provider": None,
                "model": None,
            }

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                ai_metadata=metadata_data,
            )

            db.add(assistant_message)

            conversation.updated_at = datetime.now(timezone.utc)

            db.commit()

            db.refresh(user_message)
            db.refresh(assistant_message)

            metadata = ChatMetadata(
                retrieved_count=0,
                verified_knowledge_count=0,
                verified_knowledge_topics=[],
                system_capability_count=0,
                system_capabilities=[],
                tool_used=False,
                tool_name=None,
                tool_success=None,
                attempts=0,
                used_fallback=False,
                retry_trigger_issues=[],
                provider=None,
                model=None,
            )

            return ConversationMessageResponse(
                user_message=user_message,
                assistant_message=assistant_message,
                metadata=metadata,
            )

        result = pipeline.run(
            customer_text,
            conversation_history=(conversation_history),
        )

        maybe_create_pending_cancellation(
            db=db,
            conversation_id=conversation.id,
            result=result,
        )

        retry_trigger_issues = [
            {
                "code": issue.code,
                "message": issue.message,
                "matched_text": (issue.matched_text),
            }
            for issue in result.validation_issues
        ]

        metadata_data = {
            "retrieved_count": result.retrieved_count,
            "verified_knowledge_count": result.verified_knowledge_count,
            "verified_knowledge_topics": result.verified_knowledge_topics,
            "system_capability_count": result.system_capability_count,
            "system_capabilities": result.system_capabilities,
            "tool_used": result.tool_used,
            "tool_name": result.tool_name,
            "tool_success": result.tool_success,
            "attempts": result.attempts,
            "used_fallback": result.used_fallback,
            "retry_trigger_issues": retry_trigger_issues,
            "provider": result.provider,
            "model": result.model,
        }

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=result.text,
            ai_metadata=metadata_data,
        )

        db.add(assistant_message)

        conversation.updated_at = datetime.now(timezone.utc)

        db.commit()

        db.refresh(user_message)
        db.refresh(assistant_message)

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=("ResolveAI could not process the request."),
        ) from exc

    metadata = ChatMetadata(
        retrieved_count=(result.retrieved_count),
        verified_knowledge_count=(result.verified_knowledge_count),
        verified_knowledge_topics=(result.verified_knowledge_topics),
        system_capability_count=(result.system_capability_count),
        system_capabilities=(result.system_capabilities),
        tool_used=result.tool_used,
        tool_name=result.tool_name,
        tool_success=result.tool_success,
        attempts=result.attempts,
        used_fallback=(result.used_fallback),
        retry_trigger_issues=[
            ValidationIssueResponse(
                code=issue["code"],
                message=issue["message"],
                matched_text=(issue["matched_text"]),
            )
            for issue in retry_trigger_issues
        ],
        provider=result.provider,
        model=result.model,
    )

    return ConversationMessageResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        metadata=metadata,
    )
