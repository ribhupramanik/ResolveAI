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
)
from src.api.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
)
from src.db.models import Conversation

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


DatabaseDependency = Annotated[
    Session,
    Depends(get_db),
]


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
