from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable

from app.facts.repo import FactsRepo
from app.llm.base import ToolSpec
from app.retrieval.store import DocStore


@dataclass
class ToolOutput:
    data: Any
    citations: list[str] = field(default_factory=list)


@dataclass
class Tool:
    spec: ToolSpec
    handler: Callable[[dict[str, Any]], Awaitable[ToolOutput]]


class ToolRegistry:
    def __init__(self, store: DocStore, facts: FactsRepo):
        self._store, self._facts = store, facts
        self._tools: dict[str, Tool] = {}
        self._register_all()

    @property
    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]

    async def call(self, name: str, args: dict[str, Any]) -> ToolOutput:
        if name not in self._tools:
            return ToolOutput({"error": f"Unknown tool {name}"})
        return await self._tools[name].handler(args)

    def _add(self, name: str, description: str, schema: dict, handler) -> None:
        self._tools[name] = Tool(ToolSpec(name, description, schema), handler)

    # ---- tool implementations ----
    def _register_all(self) -> None:
        v = {"type": "string", "description": "Xcode version, e.g. '26.0' or '16.4'"}

        self._add(
            "search_docs",
            "Semantic/keyword search over Xcode release notes, Apple news, OS release notes and "
            "Swift Evolution. Optionally restrict to one Xcode version or source type.",
            {"type": "object", "properties": {
                "query": {"type": "string"},
                "version": v,
                "source_type": {"type": "string", "enum": [
                    "xcode_release_notes", "system_requirements", "news",
                    "os_release_notes", "swift_evolution"]},
            }, "required": ["query"]},
            self._search_docs,
        )
        self._add(
            "diff_availability",
            "Compare two Xcode versions: structured differences (SDKs, min macOS, Swift version, "
            "deployment targets) plus release-note passages about new features, deprecations and removals.",
            {"type": "object", "properties": {"from_version": v, "to_version": v},
             "required": ["from_version", "to_version"]},
            self._diff_availability,
        )
        self._add(
            "get_toolchain_requirements",
            "Get the host macOS requirement, bundled Swift version, SDKs and minimum deployment "
            "targets for one Xcode version.",
            {"type": "object", "properties": {"version": v}, "required": ["version"]},
            self._toolchain,
        )
        self._add(
            "get_adoption_share",
            "Get adoption share data relevant to an Xcode version (e.g. OS version share for its SDK).",
            {"type": "object", "properties": {"version": v}, "required": ["version"]},
            self._adoption,
        )

    async def _search_docs(self, a: dict) -> ToolOutput:
        hits = self._store.search(a["query"], version=a.get("version"), source_type=a.get("source_type"))
        return ToolOutput([asdict(h) for h in hits], [h.url for h in hits])

    async def _diff_availability(self, a: dict) -> ToolOutput:
        frm, to = a["from_version"], a["to_version"]
        structured = self._facts.diff(frm, to)
        passages = []
        for q in ("new features", "deprecated removed", "behavior change"):
            passages += self._store.search(q, version=to, source_type="xcode_release_notes", k=3)
        # TODO: also pull removals/changes from versions strictly between frm and to.
        seen, uniq = set(), []
        for p in passages:
            if p.id not in seen:
                seen.add(p.id)
                uniq.append(p)
        return ToolOutput({"structured_diff": structured, "release_note_passages": [asdict(p) for p in uniq]},
                          [p.url for p in uniq])

    async def _toolchain(self, a: dict) -> ToolOutput:
        f = self._facts.get(a["version"])
        return ToolOutput(f or {"error": "Unknown version"}, [f["source_url"]] if f else [])

    async def _adoption(self, a: dict) -> ToolOutput:
        # TODO: source from Apple's App Store OS-adoption stats / your own telemetry.
        return ToolOutput({"error": "Not implemented", "version": a["version"]})


def serialise(out: ToolOutput) -> str:
    return json.dumps(out.data, default=str)