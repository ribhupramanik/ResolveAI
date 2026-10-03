from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.db.models import PendingAction
from src.services.pending_action_service import (
    PendingActionService,
)

CONFIRMATION_PHRASES = {
    "yes",
    "yes please",
    "confirm",
    "confirmed",
    "proceed",
    "go ahead",
    "do it",
}

REJECTION_PHRASES = {
    "no",
    "no thanks",
    "no thank you",
    "don't",
    "do not",
    "don't cancel",
    "do not cancel",
    "never mind",
    "nevermind",
    "cancel that",
}


@dataclass(frozen=True)
class PendingActionDecision:
    handled: bool
    decision: str | None
    action: PendingAction | None


def normalize_confirmation_text(
    text: str,
) -> str:
    return " ".join(text.strip().lower().rstrip(".!?").split())


def resolve_pending_action_response(
    db: Session,
    conversation_id: int,
    customer_text: str,
) -> PendingActionDecision:
    service = PendingActionService(db)

    pending_action = service.get_pending_action(conversation_id)

    # A bare "yes" or "no" means nothing operationally
    # unless this conversation actually has a pending
    # action.
    if pending_action is None:
        return PendingActionDecision(
            handled=False,
            decision=None,
            action=None,
        )

    normalized = normalize_confirmation_text(customer_text)

    if normalized in CONFIRMATION_PHRASES:
        confirmed = service.confirm_pending_action(conversation_id)

        return PendingActionDecision(
            handled=True,
            decision="confirmed",
            action=confirmed,
        )

    if normalized in REJECTION_PHRASES:
        rejected = service.reject_pending_action(conversation_id)

        return PendingActionDecision(
            handled=True,
            decision="rejected",
            action=rejected,
        )

    return PendingActionDecision(
        handled=False,
        decision=None,
        action=pending_action,
    )
