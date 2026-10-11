from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from src.api.dependencies import get_db
from src.api.routes import conversations
from src.db.database import SessionLocal, engine
from src.db.models import (
    ActionExecutionAudit,
    Conversation,
    Customer,
    Order,
    PendingAction,
    Refund,
)
from src.services.pending_action_service import (
    PendingActionService,
)


def test_execute_confirmed_refund_via_api():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    customer_id = None
    conversation_id = None
    order_id = None
    action_id = None
    order_number = None

    setup_committed = False

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            customer = Customer(
                customer_code=f"TST-RAPI-{token[:12]}",
                name="Refund API Test",
                email=f"refund-api-{token}@example.com",
            )

            conversation = Conversation(
                title="Refund API execution test",
            )

            db.add_all(
                [
                    customer,
                    conversation,
                ]
            )

            db.flush()

            customer_id = customer.id
            conversation_id = conversation.id

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            order_id = order.id
            order_number = order.order_number

            pending_service = PendingActionService(db)

            action = pending_service.create_pending_action(
                conversation_id=conversation_id,
                action_type="initiate_refund",
                target_type="order",
                target_identifier=order_number,
                action_data={
                    "order_status": "processing",
                    "payment_status": "paid",
                    "refund_amount": "1299.00",
                    "currency": "INR",
                    "eligible": True,
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            action_id = action.id

            confirmed = pending_service.confirm_pending_action(conversation_id)

            assert confirmed is not None
            assert confirmed.id == action_id
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            db.commit()
            setup_committed = True

        app = FastAPI()

        app.include_router(
            conversations.router,
            prefix="/api/v1",
        )

        def override_db():
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                yield db

        app.dependency_overrides[get_db] = override_db

        endpoint = (
            f"/api/v1/conversations/{conversation_id}"
            f"/pending-actions/{action_id}/refund/execute"
        )

        with TestClient(app) as client:
            response = client.post(endpoint)

        assert response.status_code == 200, response.text

        data = response.json()

        assert data["action_id"] == action_id

        assert data["success"] is True
        assert data["executed"] is True
        assert data["already_executed"] is False

        assert data["action_status"] == "executed"

        assert data["order_number"] == order_number
        assert data["order_status"] == "processing"

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            stored_order = db.get(
                Order,
                order_id,
            )

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is True

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            refund = refunds[0]

            assert refund.status == "processing"
            assert refund.amount == Decimal("1299.00")
            assert refund.currency == "INR"

            assert refund.initiated_at is not None
            assert refund.completed_at is None

            assert stored_action.action_data["refund_id"] == refund.id

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            audit = audits[0]

            assert audit.outcome == "executed"
            assert audit.action_performed is True

            assert audit.action_type == "initiate_refund"
            assert audit.target_type == "order"

            assert audit.details["refund_id"] == refund.id

            assert audit.details["refund_number"] == refund.refund_number

            db.rollback()

    finally:
        if setup_committed:
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


def test_unconfirmed_refund_execution_via_api_returns_409():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    customer_id = None
    conversation_id = None
    order_id = None
    action_id = None

    setup_committed = False

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            customer = Customer(
                customer_code=f"TST-RUC-{token[:12]}",
                name="Unconfirmed Refund API Test",
                email=f"unconfirmed-refund-{token}@example.com",
            )

            conversation = Conversation(
                title="Unconfirmed refund API test",
            )

            db.add_all([customer, conversation])
            db.flush()

            customer_id = customer.id
            conversation_id = conversation.id

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            order_id = order.id

            pending_service = PendingActionService(db)

            action = pending_service.create_pending_action(
                conversation_id=conversation_id,
                action_type="initiate_refund",
                target_type="order",
                target_identifier=order.order_number,
                action_data={
                    "order_status": "processing",
                    "payment_status": "paid",
                    "refund_amount": "1299.00",
                    "currency": "INR",
                    "eligible": True,
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            action_id = action.id

            assert action.status == "pending"
            assert action.confirmed_at is None

            db.commit()
            setup_committed = True

        app = FastAPI()

        app.include_router(
            conversations.router,
            prefix="/api/v1",
        )

        def override_db():
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                yield db

        app.dependency_overrides[get_db] = override_db

        endpoint = (
            f"/api/v1/conversations/{conversation_id}"
            f"/pending-actions/{action_id}/refund/execute"
        )

        with TestClient(app) as client:
            response = client.post(endpoint)

        assert response.status_code == 409

        assert response.json() == {"detail": "Refund has not been confirmed."}

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            stored_order = db.get(
                Order,
                order_id,
            )

            assert stored_action is not None
            assert stored_action.status == "pending"
            assert stored_action.confirmed_at is None

            assert stored_action.action_data["action_performed"] is False

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            assert stored_order.total_amount == Decimal("1299.00")
            assert stored_order.currency == "INR"

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert refunds == []

            audit = db.scalar(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            )

            assert audit is None

            db.rollback()

    finally:
        if setup_committed:
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


@pytest.mark.parametrize(
    (
        "scenario",
        "expected_status",
        "expected_detail",
    ),
    [
        (
            "missing_conversation",
            404,
            "Conversation not found.",
        ),
        (
            "missing_action",
            404,
            "Pending action not found.",
        ),
        (
            "foreign_conversation",
            404,
            "Pending action not found.",
        ),
        (
            "wrong_action_type",
            409,
            "Pending action cannot be executed by this endpoint.",
        ),
    ],
)
def test_refund_execution_api_validates_conversation_and_action(
    scenario,
    expected_status,
    expected_detail,
):
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    customer_id = None
    order_id = None
    conversation_ids = []
    action_ids = []

    setup_committed = False

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            customer = Customer(
                customer_code=f"TST-RAV-{token[:12]}",
                name="Refund API Validation Test",
                email=f"refund-validation-{token}@example.com",
            )

            refund_conversation = Conversation(
                title="Refund validation conversation",
            )

            other_conversation = Conversation(
                title="Other validation conversation",
            )

            db.add_all(
                [
                    customer,
                    refund_conversation,
                    other_conversation,
                ]
            )

            db.flush()

            customer_id = customer.id

            conversation_ids = [
                refund_conversation.id,
                other_conversation.id,
            ]

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            order_id = order.id

            pending_service = PendingActionService(db)

            refund_action = pending_service.create_pending_action(
                conversation_id=refund_conversation.id,
                action_type="initiate_refund",
                target_type="order",
                target_identifier=order.order_number,
                action_data={
                    "order_status": "processing",
                    "payment_status": "paid",
                    "refund_amount": "1299.00",
                    "currency": "INR",
                    "eligible": True,
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            refund_action_id = refund_action.id

            confirmed_refund = pending_service.confirm_pending_action(
                refund_conversation.id
            )

            assert confirmed_refund is not None
            assert confirmed_refund.status == "confirmed"

            cancellation_action = pending_service.create_pending_action(
                conversation_id=other_conversation.id,
                action_type="cancel_order",
                target_type="order",
                target_identifier=order.order_number,
                action_data={
                    "order_status": "processing",
                    "eligible": True,
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            cancellation_action_id = cancellation_action.id

            confirmed_cancellation = pending_service.confirm_pending_action(
                other_conversation.id
            )

            assert confirmed_cancellation is not None
            assert confirmed_cancellation.status == "confirmed"

            action_ids = [
                refund_action_id,
                cancellation_action_id,
            ]

            db.commit()
            setup_committed = True

        app = FastAPI()

        app.include_router(
            conversations.router,
            prefix="/api/v1",
        )

        def override_db():
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                yield db

        app.dependency_overrides[get_db] = override_db

        if scenario == "missing_conversation":
            request_conversation_id = 0
            request_action_id = refund_action_id

        elif scenario == "missing_action":
            request_conversation_id = conversation_ids[0]
            request_action_id = 0

        elif scenario == "foreign_conversation":
            request_conversation_id = conversation_ids[1]
            request_action_id = refund_action_id

        else:
            request_conversation_id = conversation_ids[1]
            request_action_id = cancellation_action_id

        endpoint = (
            f"/api/v1/conversations/{request_conversation_id}"
            f"/pending-actions/{request_action_id}/refund/execute"
        )

        with TestClient(app) as client:
            response = client.post(endpoint)

        assert response.status_code == expected_status

        assert response.json() == {"detail": expected_detail}

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            stored_order = db.get(
                Order,
                order_id,
            )

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            actions = db.scalars(
                select(PendingAction).where(PendingAction.id.in_(action_ids))
            ).all()

            assert len(actions) == 2

            for action in actions:
                assert action.status == "confirmed"
                assert action.confirmed_at is not None
                assert action.action_data["action_performed"] is False

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert refunds == []

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id.in_(action_ids)
                )
            ).all()

            assert audits == []

            db.rollback()

    finally:
        if setup_committed:
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id.in_(action_ids)
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(
                    delete(PendingAction).where(PendingAction.id.in_(action_ids))
                )

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id.in_(conversation_ids))
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


def test_refund_execution_api_is_idempotent_on_second_request():
    assert engine.url.database == "resolveai_test"

    token = uuid4().hex

    customer_id = None
    conversation_id = None
    order_id = None
    action_id = None

    setup_committed = False

    try:
        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            customer = Customer(
                customer_code=f"TST-RAI-{token[:12]}",
                name="Refund API Idempotency Test",
                email=f"refund-idempotency-{token}@example.com",
            )

            conversation = Conversation(
                title="Refund API idempotency test",
            )

            db.add_all([customer, conversation])
            db.flush()

            customer_id = customer.id
            conversation_id = conversation.id

            order = Order(
                order_number=f"ORD-{uuid4().int % 10**18:018d}",
                customer_id=customer_id,
                status="processing",
                payment_status="paid",
                total_amount=Decimal("1299.00"),
                currency="INR",
                shipping_address="Test address",
            )

            db.add(order)
            db.flush()

            order_id = order.id
            order_number = order.order_number

            pending_service = PendingActionService(db)

            action = pending_service.create_pending_action(
                conversation_id=conversation_id,
                action_type="initiate_refund",
                target_type="order",
                target_identifier=order_number,
                action_data={
                    "order_status": "processing",
                    "payment_status": "paid",
                    "refund_amount": "1299.00",
                    "currency": "INR",
                    "eligible": True,
                    "requires_confirmation": True,
                    "action_performed": False,
                },
            )

            action_id = action.id

            confirmed = pending_service.confirm_pending_action(conversation_id)

            assert confirmed is not None
            assert confirmed.status == "confirmed"
            assert confirmed.confirmed_at is not None

            db.commit()
            setup_committed = True

        app = FastAPI()

        app.include_router(
            conversations.router,
            prefix="/api/v1",
        )

        def override_db():
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                yield db

        app.dependency_overrides[get_db] = override_db

        endpoint = (
            f"/api/v1/conversations/{conversation_id}"
            f"/pending-actions/{action_id}/refund/execute"
        )

        with TestClient(app) as client:
            first_response = client.post(endpoint)

            assert first_response.status_code == 200

            first_data = first_response.json()

            assert first_data["success"] is True
            assert first_data["executed"] is True
            assert first_data["already_executed"] is False
            assert first_data["action_status"] == "executed"
            assert first_data["action_id"] == action_id
            assert first_data["order_number"] == order_number

            with SessionLocal() as db:
                refunds = db.scalars(
                    select(Refund).where(Refund.order_id == order_id)
                ).all()

                assert len(refunds) == 1

                original_refund_id = refunds[0].id
                original_refund_number = refunds[0].refund_number

                audits = db.scalars(
                    select(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                ).all()

                assert len(audits) == 1

                original_audit_id = audits[0].id

                db.rollback()

            second_response = client.post(endpoint)

            assert second_response.status_code == 200

            second_data = second_response.json()

            assert second_data["success"] is True
            assert second_data["executed"] is False
            assert second_data["already_executed"] is True

            assert second_data["action_id"] == action_id
            assert second_data["action_status"] == "executed"

            assert second_data["order_number"] == order_number
            assert second_data["order_status"] == "processing"

            assert second_data["reason"] == ("Refund initiation was already recorded.")

        with SessionLocal() as db:
            assert (
                db.execute(text("SELECT current_database()")).scalar_one()
                == "resolveai_test"
            )

            stored_action = db.get(
                PendingAction,
                action_id,
            )

            stored_order = db.get(
                Order,
                order_id,
            )

            assert stored_action is not None
            assert stored_action.status == "executed"
            assert stored_action.confirmed_at is not None

            assert stored_action.action_data["action_performed"] is True

            assert stored_order is not None
            assert stored_order.status == "processing"
            assert stored_order.payment_status == "paid"

            refunds = db.scalars(
                select(Refund).where(Refund.order_id == order_id)
            ).all()

            assert len(refunds) == 1

            refund = refunds[0]

            assert refund.id == original_refund_id
            assert refund.refund_number == original_refund_number

            assert refund.status == "processing"
            assert refund.amount == Decimal("1299.00")
            assert refund.currency == "INR"

            assert stored_action.action_data["refund_id"] == original_refund_id

            assert stored_action.action_data["refund_number"] == original_refund_number

            audits = db.scalars(
                select(ActionExecutionAudit).where(
                    ActionExecutionAudit.pending_action_id == action_id
                )
            ).all()

            assert len(audits) == 1

            audit = audits[0]

            assert audit.id == original_audit_id
            assert audit.outcome == "executed"
            assert audit.action_performed is True

            assert audit.details["refund_id"] == original_refund_id

            assert audit.details["refund_number"] == original_refund_number

            db.rollback()

    finally:
        if setup_committed:
            with SessionLocal() as db:
                assert (
                    db.execute(text("SELECT current_database()")).scalar_one()
                    == "resolveai_test"
                )

                db.execute(
                    delete(ActionExecutionAudit).where(
                        ActionExecutionAudit.pending_action_id == action_id
                    )
                )

                db.execute(delete(Refund).where(Refund.order_id == order_id))

                db.execute(delete(PendingAction).where(PendingAction.id == action_id))

                db.execute(delete(Order).where(Order.id == order_id))

                db.execute(
                    delete(Conversation).where(Conversation.id == conversation_id)
                )

                db.execute(delete(Customer).where(Customer.id == customer_id))

                db.commit()


