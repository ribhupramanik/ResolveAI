import pytest

from src.db.database import SessionLocal
from src.db.models import Conversation
from src.rag.pipeline import RAGResult
from src.services.pending_action_integration import (
    maybe_create_pending_cancellation,
)
from src.services.pending_action_service import (
    PendingActionService,
)


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def conversation(db):
    conversation = Conversation(
        title="Pending integration test",
    )

    db.add(conversation)
    db.flush()

    return conversation


def make_result(
    *,
    tool_name="check_cancellation_eligibility",
    tool_success=True,
    tool_data=None,
    used_fallback=False,
):
    return RAGResult(
        text="Test response.",
        provider="test",
        model="test",
        retrieved_count=0,
        verified_knowledge_count=0,
        verified_knowledge_topics=[],
        system_capability_count=0,
        system_capabilities=[],
        attempts=1,
        used_fallback=used_fallback,
        validation_issues=[],
        tool_used=tool_name is not None,
        tool_name=tool_name,
        tool_success=tool_success,
        tool_data=tool_data,
    )


def test_eligible_order_creates_pending_action(
    db,
    conversation,
):
    result = make_result(
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "eligible": True,
            "reason": ("Order is still processing."),
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    created = maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=result,
    )

    assert created is not None

    assert created.action_type == "cancel_order"
    assert created.target_type == "order"

    assert created.target_identifier == "ORD-10002"

    assert created.status == "pending"

    assert created.action_data["eligible"] is True

    assert created.action_data["requires_confirmation"] is True

    assert created.action_data["action_performed"] is False


def test_ineligible_order_does_not_create_action(
    db,
    conversation,
):
    result = make_result(
        tool_data={
            "found": True,
            "order_number": "ORD-10001",
            "status": "shipped",
            "eligible": False,
            "requires_confirmation": False,
            "action_performed": False,
        },
    )

    created = maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=result,
    )

    assert created is None

    service = PendingActionService(db)

    assert service.get_pending_action(conversation.id) is None


def test_failed_tool_does_not_create_action(
    db,
    conversation,
):
    result = make_result(
        tool_success=False,
        tool_data={
            "found": False,
            "order_number": "ORD-99999",
        },
    )

    created = maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=result,
    )

    assert created is None


def test_fallback_response_does_not_create_action(
    db,
    conversation,
):
    result = make_result(
        used_fallback=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    created = maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=result,
    )

    assert created is None


def test_second_eligible_order_supersedes_first(
    db,
    conversation,
):
    first = make_result(
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=first,
    )

    second = make_result(
        tool_data={
            "found": True,
            "order_number": "ORD-10003",
            "status": "processing",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    created = maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=second,
    )

    service = PendingActionService(db)

    pending = service.get_pending_action(conversation.id)

    assert pending is not None
    assert pending.id == created.id

    assert pending.target_identifier == "ORD-10003"


def test_non_cancellation_tool_does_not_create_action(
    db,
    conversation,
):
    result = make_result(
        tool_name="get_order",
        tool_success=True,
        tool_data={
            "found": True,
            "order_number": "ORD-10002",
            "status": "processing",
        },
    )

    created = maybe_create_pending_cancellation(
        db=db,
        conversation_id=conversation.id,
        result=result,
    )

    assert created is None

    service = PendingActionService(db)

    assert (
        service.get_pending_action(
            conversation.id
        )
        is None
    )