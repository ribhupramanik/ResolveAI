from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    data: dict[str, Any]
    error: str | None = None