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
from src.api.schemas.action_execution import (
    CancellationExecutionResponse,
)
from src.api.schemas.chat import (
    ChatMetadata,
    ToolExecutionMetadata,
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
from src.api.schemas.pending_action import (
    PendingActionResponse,
)
from src.db.models import (
    Conversation,
    Message,
    PendingAction,
)
from src.rag.conversation import (
    ConversationTurn,
)
from src.rag.pipeline import (
    ResolveAIPipeline,
)
from src.services.cancellation_execution_service import (
    CancellationExecutionService,
)
from src.services.pending_action_confirmation import (
    resolve_pending_action_response,
)
from src.services.pending_action_integration import (
    maybe_create_pending_cancellation,
    maybe_create_pending_refund,
)
from src.services.pending_action_service import (
    CONFIRMED,
    EXECUTED,
    INVALIDATED,
    PENDING,
    REJECTED,
    PendingActionService,
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
    "/{conversation_id}/pending-action",
    response_model=PendingActionResponse | None,
)
def get_pending_action(
    conversation_id: int,
    db: DatabaseDependency,
) -> PendingActionResponse | None:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    service = PendingActionService(db)

    pending_action = service.get_pending_action(conversation_id)

    if pending_action is None:
        return None

    return PendingActionResponse(
        id=pending_action.id,
        action_type=pending_action.action_type,
        target_identifier=(pending_action.target_identifier),
        status=pending_action.status,
    )


@router.post(
    "/{conversation_id}/pending-actions/{action_id}/execute",
    response_model=CancellationExecutionResponse,
)
def execute_pending_action(
    conversation_id: int,
    action_id: int,
    db: DatabaseDependency,
) -> CancellationExecutionResponse:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    # Read only the fields required for ownership/type
    # validation here.
    #
    # Do not load the PendingAction ORM object before
    # CancellationExecutionService acquires its row lock.
    action_info = db.execute(
        select(
            PendingAction.conversation_id,
            PendingAction.action_type,
            PendingAction.target_type,
        ).where(PendingAction.id == action_id)
    ).one_or_none()

    if action_info is None or action_info.conversation_id != conversation.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending action not found.",
        )

    if action_info.action_type != "cancel_order" or action_info.target_type != "order":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=("Pending action cannot be executed by this endpoint."),
        )

    try:
        result = CancellationExecutionService(db).execute(action_id)

        # A successful/idempotent execution must commit.
        #
        # INVALIDATED must also commit because the service
        # records the invalidation and its audit row.
        should_commit = result.success or result.action_status == INVALIDATED

        if not should_commit:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.reason,
            )

        db.commit()

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=("Cancellation execution failed."),
        ) from exc

    return CancellationExecutionResponse(
        action_id=action_id,
        success=result.success,
        executed=result.executed,
        already_executed=(result.already_executed),
        action_status=result.action_status,
        order_number=result.order_number,
        order_status=result.order_status,
        reason=result.reason,
    )


@router.post(
    "/{conversation_id}/pending-actions/{action_id}/confirm-and-execute",
    response_model=CancellationExecutionResponse,
)
def confirm_and_execute_pending_action(
    conversation_id: int,
    action_id: int,
    db: DatabaseDependency,
) -> CancellationExecutionResponse:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    try:
        # This is the transaction's first authoritative
        # read of the action. Lock it immediately.
        action = db.scalar(
            select(PendingAction).where(PendingAction.id == action_id).with_for_update()
        )

        if action is None or action.conversation_id != conversation.id:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending action not found.",
            )

        if action.action_type != "cancel_order" or action.target_type != "order":
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Pending action cannot be executed by this endpoint."),
            )

        # Clicking the explicit Confirm cancellation
        # button is the confirmation event.
        if action.status == PENDING:
            action.status = CONFIRMED
            action.confirmed_at = datetime.now(timezone.utc)

            db.flush()

        # Allow a retry after confirmation or execution.
        # EXECUTED is handled idempotently by the
        # execution service.
        elif action.status not in {
            CONFIRMED,
            EXECUTED,
        }:
            current_status = action.status

            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cancellation cannot be confirmed "
                    f"because the action is "
                    f"'{current_status}'."
                ),
            )

        result = CancellationExecutionService(db).execute(action_id)

        should_commit = result.success or result.action_status == INVALIDATED

        if not should_commit:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.reason,
            )

        # Persist the customer-visible result as part of the
        # same transaction as the order/action/audit changes.
        #
        # Do not create another message for an idempotent
        # retry after the cancellation has already executed.
        assistant_text = None

        if result.executed:
            assistant_text = (
                f"Order {result.order_number} has been cancelled successfully."
            )

        elif result.action_status == INVALIDATED:
            target_identifier = result.order_number or action.target_identifier

            assistant_text = (
                f"The cancellation for "
                f"{target_identifier} "
                f"could not be completed. "
                f"{result.reason}"
            )

        if assistant_text is not None:
            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                ai_metadata=None,
            )

            db.add(assistant_message)

            conversation.updated_at = datetime.now(timezone.utc)

        db.commit()

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=("Cancellation confirmation and execution failed."),
        ) from exc

    return CancellationExecutionResponse(
        action_id=action_id,
        success=result.success,
        executed=result.executed,
        already_executed=(result.already_executed),
        action_status=result.action_status,
        order_number=result.order_number,
        order_status=result.order_status,
        reason=result.reason,
    )


@router.post(
    "/{conversation_id}/pending-actions/{action_id}/reject",
    response_model=PendingActionResponse,
)
def reject_pending_action_by_id(
    conversation_id: int,
    action_id: int,
    db: DatabaseDependency,
) -> PendingActionResponse:

    conversation = db.get(
        Conversation,
        conversation_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    try:
        # Lock the exact action selected by the UI.
        action = db.scalar(
            select(PendingAction).where(PendingAction.id == action_id).with_for_update()
        )

        if action is None or action.conversation_id != conversation.id:
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pending action not found.",
            )

        if action.action_type != "cancel_order" or action.target_type != "order":
            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Pending action cannot be rejected by this endpoint."),
            )

        # First rejection:
        # pending -> rejected
        if action.status == PENDING:
            action.status = REJECTED

            assistant_text = (
                f"The pending cancellation request for "
                f"{action.target_identifier} "
                f"has been rejected. "
                f"No cancellation has been performed."
            )

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                ai_metadata=None,
            )

            db.add(assistant_message)

            conversation.updated_at = datetime.now(timezone.utc)

            db.flush()

        # Retry/double-click after rejection:
        # return success without writing another message.
        elif action.status == REJECTED:
            pass

        else:
            current_status = action.status

            db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Cancellation cannot be rejected "
                    f"because the action is "
                    f"'{current_status}'."
                ),
            )

        db.commit()

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=(status.HTTP_500_INTERNAL_SERVER_ERROR),
            detail=("Cancellation rejection failed."),
        ) from exc

    return PendingActionResponse(
        id=action.id,
        action_type=action.action_type,
        target_identifier=(action.target_identifier),
        status=action.status,
    )


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
                if (
                    action.action_type != "cancel_order"
                    or action.target_type != "order"
                ):
                    if (
                        action.action_type == "initiate_refund"
                        and action.target_type == "order"
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Refund execution is not available yet.",
                        )

                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Pending action cannot be executed through chat.",
                    )

                # Existing cancellation execution logic.
                execution_result = CancellationExecutionService(db).execute(action.id)

                should_commit = (
                    execution_result.success
                    or execution_result.action_status == INVALIDATED
                )

                if not should_commit:
                    raise RuntimeError(execution_result.reason)

                if execution_result.executed:
                    assistant_text = (
                        f"Order "
                        f"{execution_result.order_number} "
                        f"has been cancelled successfully."
                    )

                elif execution_result.already_executed:
                    assistant_text = (
                        f"Order {execution_result.order_number} was already cancelled."
                    )

                elif execution_result.action_status == INVALIDATED:
                    target_identifier = (
                        execution_result.order_number or action.target_identifier
                    )

                    assistant_text = (
                        f"The cancellation for "
                        f"{target_identifier} "
                        f"could not be completed. "
                        f"{execution_result.reason}"
                    )

                else:
                    raise RuntimeError("Unexpected cancellation execution result.")

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
                "tool_executions": [],
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

            # This is the only commit.
            #
            # For typed confirmation it atomically commits:
            # - the user's "yes" message
            # - pending -> confirmed
            # - order cancellation / invalidation
            # - pending -> executed / invalidated
            # - execution audit
            # - assistant result message
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
                tool_executions=[],
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
                pending_action=None,
            )

        result = pipeline.run(
            customer_text,
            conversation_history=(conversation_history),
        )

        # Create a cancellation PendingAction only when
        # cancellation eligibility requires confirmation.
        maybe_create_pending_cancellation(
            db=db,
            conversation_id=conversation.id,
            result=result,
        )

        # Create a refund PendingAction only when
        # refund eligibility requires confirmation.
        # This does not initiate or execute a refund.
        maybe_create_pending_refund(
            db=db,
            conversation_id=conversation.id,
            result=result,
        )

        pending_action_service = PendingActionService(db)

        pending_action = pending_action_service.get_pending_action(
            conversation.id
        )

        retry_trigger_issues = [
            {
                "code": issue.code,
                "message": issue.message,
                "matched_text": (issue.matched_text),
            }
            for issue in result.validation_issues
        ]

        tool_executions = [
            {
                "tool_name": tool_result.tool_name,
                "success": tool_result.success,
            }
            for tool_result in result.tool_results
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
            "tool_executions": tool_executions,
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

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="ResolveAI could not process the request.",
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
        tool_executions=[
            ToolExecutionMetadata(
                tool_name=execution["tool_name"],
                success=execution["success"],
            )
            for execution in tool_executions
        ],
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

    pending_action_response = None

    if pending_action is not None:
        pending_action_response = PendingActionResponse(
            id=pending_action.id,
            action_type=pending_action.action_type,
            target_identifier=(pending_action.target_identifier),
            status=pending_action.status,
        )

    return ConversationMessageResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        metadata=metadata,
        pending_action=pending_action_response,
    )


