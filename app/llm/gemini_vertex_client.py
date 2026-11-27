from __future__ import annotations

import json
from typing import Any

from .base import LLMClient, LLMResponse, Message, ToolCall, ToolSpec, Usage


class GeminiVertexClient(LLMClient):
    def __init__(self, project: str, region: str, model: str):
        from google import genai
        self._types = __import__("google.genai.types", fromlist=["types"])
        self._client = genai.Client(vertexai=True, project=project, location=region)
        self._model = model

    def _to_contents(self, messages: list[Message]) -> list[Any]:
        t = self._types
        contents = []
        for m in messages:
            parts = []
            if m.text:
                parts.append(t.Part(text=m.text))
            for tc in m.tool_calls:
                parts.append(t.Part(function_call=t.FunctionCall(name=tc.name, args=tc.arguments)))
            for tr in m.tool_results:
                parts.append(t.Part(function_response=t.FunctionResponse(
                    name=tr.tool_name, response={"result": json.loads(tr.content)})))
            contents.append(t.Content(role="model" if m.role == "assistant" else "user", parts=parts))
        return contents

    async def complete(self, *, system, messages, tools=None, max_tokens=2048):
        t = self._types
        config = t.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=0.0,
            tools=[t.Tool(function_declarations=[
                t.FunctionDeclaration(name=s.name, description=s.description, parameters=s.input_schema)
                for s in tools
            ])] if tools else None,
        )
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=self._to_contents(messages), config=config)

        parts = resp.candidates[0].content.parts or []
        text = "".join(p.text for p in parts if getattr(p, "text", None))
        # Gemini has no call IDs; synthesise from name + index.
        calls = [
            ToolCall(id=f"{p.function_call.name}-{i}", name=p.function_call.name,
                     arguments=dict(p.function_call.args or {}))
            for i, p in enumerate(parts) if getattr(p, "function_call", None)
        ]
        um = resp.usage_metadata
        return LLMResponse(
            text=text, tool_calls=calls,
            stop_reason="tool_use" if calls else "end_turn",
            usage=Usage(um.prompt_token_count or 0, um.candidates_token_count or 0) if um else Usage(),
        )