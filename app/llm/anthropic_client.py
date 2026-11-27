from __future__ import annotations

from typing import Any

from .base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec, Usage

_STOP_MAP = {"end_turn": "end_turn", "tool_use": "tool_use", "max_tokens": "max_tokens"}


def _to_wire(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.provider_content is not None:
            out.append({"role": m.role, "content": m.provider_content})
            continue
        blocks: list[dict[str, Any]] = []
        if m.text:
            blocks.append({"type": "text", "text": m.text})
        for tc in m.tool_calls:
            blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
        for tr in m.tool_results:
            blocks.append({
                "type": "tool_result",
                "tool_use_id": tr.tool_call_id,
                "content": tr.content,
                "is_error": tr.is_error,
            })
        out.append({"role": m.role, "content": blocks})
    return out


class _AnthropicMessagesClient(LLMClient):
    """Shared logic: the direct API and Claude-on-Vertex use the same Messages shape."""

    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    async def complete(self, *, system, messages, tools=None, max_tokens=16000):
        kwargs: dict[str, Any] = dict(
            model=self._model,
            system=system,
            messages=_to_wire(messages),
            max_tokens=max_tokens,  # covers thinking as well as the reply
        )
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        resp = await self._client.messages.create(**kwargs)

        text = "".join(b.text for b in resp.content if b.type == "text")
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
            for b in resp.content if b.type == "tool_use"
        ]
        return LLMResponse(
            text=text,
            tool_calls=calls,
            stop_reason=_STOP_MAP.get(resp.stop_reason, "other"),
            usage=Usage(resp.usage.input_tokens, resp.usage.output_tokens),
            provider_content=list(resp.content),
        )


class AnthropicDirectClient(_AnthropicMessagesClient):
    def __init__(self, api_key: str, model: str):
        from anthropic import AsyncAnthropic  # lazy import: SDK optional until used
        super().__init__(AsyncAnthropic(api_key=api_key), model)


class AnthropicVertexClient(_AnthropicMessagesClient):
    """Claude served through Google Cloud Vertex AI (ADC auth)."""

    def __init__(self, project: str, region: str, model: str):
        from anthropic import AsyncAnthropicVertex
        super().__init__(AsyncAnthropicVertex(project_id=project, region=region), model)