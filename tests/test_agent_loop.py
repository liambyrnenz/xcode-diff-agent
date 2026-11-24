import pytest

from app.agent.loop import Agent
from app.agent.tools import ToolRegistry
from app.facts.repo import FactsRepo
from app.llm.base import LLMClient, LLMResponse, ToolCall
from app.retrieval.store import InMemoryKeywordStore
from pathlib import Path


class FakeLLM(LLMClient):
    def __init__(self):
        self.turn = 0

    async def complete(self, *, system, messages, tools=None, **kw):
        self.turn += 1
        if self.turn == 1:
            return LLMResponse("", [ToolCall("1", "get_toolchain_requirements", {"version": "26.0"})], "tool_use")
        return LLMResponse("Xcode 26.0 needs macOS 15.6.", [], "end_turn")


@pytest.mark.asyncio
async def test_agent_calls_tool_then_answers():
    tools = ToolRegistry(InMemoryKeywordStore(), FactsRepo(Path("data/xcode_versions.json")))
    result = await Agent(FakeLLM(), tools).run("What does Xcode 26 need?")
    assert "15.6" in result.answer
    assert result.tool_trace[0]["tool"] == "get_toolchain_requirements"