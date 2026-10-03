import pytest

from src.db.database import SessionLocal
from src.db.models import Conversation
from src.services.pending_action_confirmation import (
    resolve_pending_action_response,
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
        title="Confirmation test",
    )

    db.add(conversation)
    db.flush()

    return conversation


@pytest.fixture
def pending_action(
    db,
    conversation,
):
    service = PendingActionService(db)

    return service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10002",
        action_data={
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )


@pytest.mark.parametrize(
    "text",
    [
        "yes",
        "Yes",
        "yes please",
        "confirm",
        "proceed",
        "go ahead",
        "do it",
        "Yes!",
    ],
)
def test_explicit_confirmation_confirms_pending_action(
    db,
    conversation,
    pending_action,
    text,
):
    result = resolve_pending_action_response(
        db=db,
        conversation_id=conversation.id,
        customer_text=text,
    )

    assert result.handled is True
    assert result.decision == "confirmed"
    assert result.action is not None

    assert result.action.id == pending_action.id
    assert result.action.status == "confirmed"
    assert result.action.confirmed_at is not None


@pytest.mark.parametrize(
    "text",
    [
        "no",
        "No",
        "no thanks",
        "don't cancel",
        "do not cancel",
        "never mind",
        "Never mind!",
    ],
)
def test_explicit_rejection_rejects_pending_action(
    db,
    conversation,
    pending_action,
    text,
):
    result = resolve_pending_action_response(
        db=db,
        conversation_id=conversation.id,
        customer_text=text,
    )

    assert result.handled is True
    assert result.decision == "rejected"
    assert result.action is not None

    assert result.action.id == pending_action.id
    assert result.action.status == "rejected"
    assert result.action.confirmed_at is None


def test_yes_without_pending_action_is_not_handled(
    db,
    conversation,
):
    result = resolve_pending_action_response(
        db=db,
        conversation_id=conversation.id,
        customer_text="yes",
    )

    assert result.handled is False
    assert result.decision is None
    assert result.action is None


def test_longer_message_is_not_treated_as_confirmation(
    db,
    conversation,
    pending_action,
):
    result = resolve_pending_action_response(
        db=db,
        conversation_id=conversation.id,
        customer_text=("Yes, but what happens to my payment?"),
    )

    assert result.handled is False
    assert result.decision is None

    service = PendingActionService(db)

    still_pending = service.get_pending_action(conversation.id)

    assert still_pending is not None
    assert still_pending.status == "pending"


def test_confirmation_does_not_perform_action(
    db,
    conversation,
    pending_action,
):
    result = resolve_pending_action_response(
        db=db,
        conversation_id=conversation.id,
        customer_text="yes",
    )

    assert result.action is not None

    assert result.action.action_data["action_performed"] is False

    assert result.action.status == "confirmed"
