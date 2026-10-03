import pytest

from src.db.database import SessionLocal
from src.db.models import Conversation
from src.services.pending_action_service import (
    CONFIRMED,
    PENDING,
    REJECTED,
    SUPERSEDED,
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
        title="Pending action test",
    )

    db.add(conversation)
    db.flush()

    return conversation


def test_create_pending_action(
    db,
    conversation,
):
    service = PendingActionService(db)

    action = service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ord-10002",
        action_data={
            "order_status": "processing",
            "eligible": True,
            "requires_confirmation": True,
            "action_performed": False,
        },
    )

    assert action.id is not None
    assert action.conversation_id == conversation.id

    assert action.action_type == "cancel_order"
    assert action.target_type == "order"
    assert action.target_identifier == "ORD-10002"

    assert action.status == PENDING

    assert action.action_data["eligible"] is True
    assert (
        action.action_data["requires_confirmation"]
        is True
    )
    assert (
        action.action_data["action_performed"]
        is False
    )


def test_get_pending_action(
    db,
    conversation,
):
    service = PendingActionService(db)

    created = service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10002",
    )

    found = service.get_pending_action(
        conversation.id
    )

    assert found is not None
    assert found.id == created.id
    assert found.target_identifier == "ORD-10002"


def test_confirm_pending_action(
    db,
    conversation,
):
    service = PendingActionService(db)

    service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10002",
    )

    confirmed = service.confirm_pending_action(
        conversation.id
    )

    assert confirmed is not None
    assert confirmed.status == CONFIRMED
    assert confirmed.confirmed_at is not None

    assert (
        service.get_pending_action(
            conversation.id
        )
        is None
    )


def test_reject_pending_action(
    db,
    conversation,
):
    service = PendingActionService(db)

    service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10002",
    )

    rejected = service.reject_pending_action(
        conversation.id
    )

    assert rejected is not None
    assert rejected.status == REJECTED
    assert rejected.confirmed_at is None

    assert (
        service.get_pending_action(
            conversation.id
        )
        is None
    )


def test_new_action_supersedes_existing_action(
    db,
    conversation,
):
    service = PendingActionService(db)

    first = service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10002",
    )

    second = service.create_pending_action(
        conversation_id=conversation.id,
        action_type="cancel_order",
        target_type="order",
        target_identifier="ORD-10003",
    )

    assert first.status == SUPERSEDED
    assert second.status == PENDING

    pending = service.get_pending_action(
        conversation.id
    )

    assert pending is not None
    assert pending.id == second.id
    assert pending.target_identifier == "ORD-10003"


def test_confirm_returns_none_when_no_action_pending(
    db,
    conversation,
):
    service = PendingActionService(db)

    result = service.confirm_pending_action(
        conversation.id
    )

    assert result is None


def test_reject_returns_none_when_no_action_pending(
    db,
    conversation,
):
    service = PendingActionService(db)

    result = service.reject_pending_action(
        conversation.id
    )

    assert result is None