from decimal import Decimal
from uuid import uuid4

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
