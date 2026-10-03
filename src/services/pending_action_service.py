from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import PendingAction

PENDING = "pending"
CONFIRMED = "confirmed"
REJECTED = "rejected"
SUPERSEDED = "superseded"
EXECUTED = "executed"
INVALIDATED = "invalidated"


class PendingActionService:
    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def get_pending_action(
        self,
        conversation_id: int,
    ) -> PendingAction | None:
        statement = (
            select(PendingAction)
            .where(
                PendingAction.conversation_id == conversation_id,
                PendingAction.status == PENDING,
            )
            .order_by(
                PendingAction.created_at.desc(),
                PendingAction.id.desc(),
            )
        )

        return self.db.scalars(statement).first()

    def create_pending_action(
        self,
        conversation_id: int,
        action_type: str,
        target_type: str,
        target_identifier: str,
        action_data: dict[str, Any] | None = None,
    ) -> PendingAction:
        self._supersede_existing(
            conversation_id=conversation_id,
        )

        pending_action = PendingAction(
            conversation_id=conversation_id,
            action_type=action_type,
            target_type=target_type,
            target_identifier=(target_identifier.strip().upper()),
            status=PENDING,
            action_data=dict(action_data or {}),
        )

        self.db.add(pending_action)
        self.db.flush()

        return pending_action

    def confirm_pending_action(
        self,
        conversation_id: int,
    ) -> PendingAction | None:
        pending_action = self.get_pending_action(
            conversation_id,
        )

        if pending_action is None:
            return None

        pending_action.status = CONFIRMED
        pending_action.confirmed_at = datetime.now(timezone.utc)

        self.db.flush()

        return pending_action

    def reject_pending_action(
        self,
        conversation_id: int,
    ) -> PendingAction | None:
        pending_action = self.get_pending_action(
            conversation_id,
        )

        if pending_action is None:
            return None

        pending_action.status = REJECTED

        self.db.flush()

        return pending_action

    def _supersede_existing(
        self,
        conversation_id: int,
    ) -> None:
        statement = select(PendingAction).where(
            PendingAction.conversation_id == conversation_id,
            PendingAction.status == PENDING,
        )

        existing_actions = self.db.scalars(statement).all()

        for existing_action in existing_actions:
            existing_action.status = SUPERSEDED

        if existing_actions:
            self.db.flush()
