from pydantic import BaseModel


class PendingActionResponse(BaseModel):
    id: int
    action_type: str
    target_identifier: str
    status: str