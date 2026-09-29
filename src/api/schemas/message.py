from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from src.api.schemas.chat import (
    ChatMetadata,
)


class MessageCreate(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    ai_metadata: dict | None = None
    created_at: datetime


class ConversationMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    metadata: ChatMetadata
