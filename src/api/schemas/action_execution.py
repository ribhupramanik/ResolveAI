from pydantic import BaseModel


class CancellationExecutionResponse(BaseModel):
    action_id: int
    success: bool
    executed: bool
    already_executed: bool

    action_status: str | None

    order_number: str | None
    order_status: str | None

    reason: str
