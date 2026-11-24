from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FactsRepo:
    """Structured, authoritative per-version facts (ideally extracted at ingestion
    from the system requirements page). Prefer these over LLM-read prose for
    anything numeric or tabular."""

    def __init__(self, path: Path):
        self._data: dict[str, dict[str, Any]] = json.loads(path.read_text()) if path.exists() else {}

    def versions(self) -> list[str]:
        return sorted(self._data)

    def get(self, version: str) -> dict[str, Any] | None:
        return self._data.get(version)

    def diff(self, a: str, b: str) -> dict[str, Any]:
        fa, fb = self._data.get(a), self._data.get(b)
        if fa is None or fb is None:
            return {"error": f"Unknown version(s): {[v for v, f in ((a, fa), (b, fb)) if f is None]}"}
        changes: dict[str, Any] = {}
        for key in ("min_macos", "swift_version"):
            if fa.get(key) != fb.get(key):
                changes[key] = {"from": fa.get(key), "to": fb.get(key)}
        for group in ("sdks", "min_deployment_targets"):
            ga, gb = fa.get(group, {}), fb.get(group, {})
            delta = {p: {"from": ga.get(p), "to": gb.get(p)}
                     for p in set(ga) | set(gb) if ga.get(p) != gb.get(p)}
            if delta:
                changes[group] = delta
        return changes