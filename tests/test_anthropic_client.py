"""Runs the real Anthropic SDK against a mocked connection: no network or API key."""
import json
from pathlib import Path

import pytest

pytest.importorskip("anthropic")

import httpx2
from anthropic import AsyncAnthropic

from app.agent.loop import Agent
from app.agent.tools import ToolRegistry
from app.facts.repo import FactsRepo
from app.llm.anthropic_client import AnthropicDirectClient
from app.retrieval.store import InMemoryKeywordStore

THINKING = {"type": "thinking", "thinking": "", "signature": "sig-1"}
TOOL_USE = {"type": "tool_use", "id": "toolu_1", "name": "get_toolchain_requirements",
            "input": {"version": "26.0"}}
ANSWER = {"type": "text", "text": "Xcode 26.0 needs macOS 15.6."}


def message_response(content, stop_reason):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
            "content": content, "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1}}


def mock_sdk(replies, sent):
    def handler(request):
        sent.append((request, json.loads(request.content)))
        return httpx2.Response(200, json=replies[len(sent) - 1])

    return AsyncAnthropic(api_key="test-key", max_retries=0,
                          http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))


def direct_client(replies, sent):
    client = AnthropicDirectClient(api_key="test-key", model="claude-sonnet-5-5")
    client._client = mock_sdk(replies, sent)
    return client


async def run_agent(llm):
    tools = ToolRegistry(InMemoryKeywordStore(), FactsRepo(Path("data/xcode_versions.json")))
    return await Agent(llm, tools).run("What does Xcode 26 need?")


async def test_tool_loop_replays_thinking_and_sends_no_sampling_params():
    sent = []
    llm = direct_client([message_response([THINKING, TOOL_USE], "tool_use"),
                         message_response([ANSWER], "end_turn")], sent)

    result = await run_agent(llm)

    assert result.answer == ANSWER["text"]
    for _, body in sent:
        assert not {"temperature", "top_p", "top_k"} & body.keys()
        assert body["max_tokens"] == 16000
    assistant, tool_turn = sent[1][1]["messages"][1:]
    assert assistant == {"role": "assistant", "content": [THINKING, TOOL_USE]}
    assert tool_turn["content"][0]["tool_use_id"] == "toolu_1"


@pytest.mark.parametrize("content", [[ANSWER, TOOL_USE], [THINKING]])
async def test_max_tokens_marks_answer_incomplete_and_runs_no_tools(content):
    sent = []
    result = await run_agent(direct_client([message_response(content, "max_tokens")], sent))

    assert result.answer.endswith("[Incomplete: the model reached its output token limit.]")
    assert result.tool_trace == [] and len(sent) == 1
