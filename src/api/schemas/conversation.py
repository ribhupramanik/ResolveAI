from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ConversationCreate(BaseModel):
    title: str | None = Field(
        default=None,
        max_length=255,
    )


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime
