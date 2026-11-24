from __future__ import annotations

from dataclasses import dataclass, field

from app.llm.base import LLMClient, Message, ToolResult

from .prompts import SYSTEM_PROMPT
from .tools import ToolRegistry, serialise


@dataclass
class AgentResult:
    answer: str
    citations: list[str] = field(default_factory=list)
    tool_trace: list[dict] = field(default_factory=list)
    steps: int = 0


class Agent:
    def __init__(self, llm: LLMClient, tools: ToolRegistry, max_steps: int = 8):
        self._llm, self._tools, self._max_steps = llm, tools, max_steps

    async def run(self, question: str, history: list[Message] | None = None) -> AgentResult:
        messages = [*(history or []), Message(role="user", text=question)]
        citations: list[str] = []
        trace: list[dict] = []

        for step in range(1, self._max_steps + 1):
            resp = await self._llm.complete(
                system=SYSTEM_PROMPT, messages=messages, tools=self._tools.specs)
            messages.append(resp.to_message())

            if not resp.tool_calls:
                return AgentResult(resp.text, sorted(set(citations)), trace, step)

            results = []
            for call in resp.tool_calls:  # TODO: asyncio.gather for parallel calls
                try:
                    out = await self._tools.call(call.name, call.arguments)
                    citations += out.citations
                    results.append(ToolResult(call.id, call.name, serialise(out)))
                    trace.append({"tool": call.name, "args": call.arguments})
                except Exception as e:  # surface errors to the model so it can recover
                    results.append(ToolResult(call.id, call.name, str(e), is_error=True))
            messages.append(Message(role="user", tool_results=results))

        return AgentResult("I couldn't complete this within the step limit.",
                           sorted(set(citations)), trace, self._max_steps)