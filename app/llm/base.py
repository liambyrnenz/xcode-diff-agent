from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    tool_name: str
    content: str  # JSON-serialised string
    is_error: bool = False


@dataclass
class Message:
    """Neutral message. Exactly one of the three shapes is used per message:
    - user text:          role="user", text=...
    - assistant output:   role="assistant", text=... and/or tool_calls=[...]
    - tool results:       role="user", tool_results=[...]
    """
    role: Literal["user", "assistant"]
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    # Assistant turns only: the backend's own content blocks. A client that sets this
    # replays it as-is, keeping blocks the neutral fields can't express (e.g. thinking).
    provider_content: list[Any] | None = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "other"]
    usage: Usage = field(default_factory=Usage)
    provider_content: list[Any] | None = None

    def to_message(self) -> Message:
        return Message(role="assistant", text=self.text or None, tool_calls=self.tool_calls,
                       provider_content=self.provider_content)


class LLMClient(ABC):
    """Swap implementations via app/llm/factory.py; nothing else should import an SDK."""

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 16000,
    ) -> LLMResponse: ...