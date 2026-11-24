from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class Chunk:
    id: str
    text: str
    heading: str
    version: str | None      # e.g. "26.0"; None for version-agnostic docs
    source_type: str         # xcode_release_notes | system_requirements | news | os_release_notes | swift_evolution
    url: str


class DocStore(Protocol):
    def add(self, chunks: list[Chunk]) -> None: ...
    def search(self, query: str, *, version: str | None = None,
               source_type: str | None = None, k: int = 6) -> list[Chunk]: ...


_tok = re.compile(r"[a-z0-9_.]+")


def _tokens(s: str) -> list[str]:
    return _tok.findall(s.lower())


class InMemoryKeywordStore:
    """Placeholder BM25-ish store. Swap for pgvector / Vertex Vector Search / Chroma
    behind the same DocStore protocol (ideally hybrid: keyword + embeddings)."""

    def __init__(self, path: Path | None = None):
        self._path = path
        self._chunks: list[Chunk] = []
        if path and path.exists():
            self._chunks = [Chunk(**d) for d in json.loads(path.read_text())]

    def add(self, chunks: list[Chunk]) -> None:
        self._chunks.extend(chunks)
        if self._path:
            self._path.write_text(json.dumps([asdict(c) for c in self._chunks]))

    def search(self, query, *, version=None, source_type=None, k=6):
        q = _tokens(query)
        n = len(self._chunks) or 1
        df = Counter(t for c in self._chunks for t in set(_tokens(c.text + " " + c.heading)))
        scored = []
        for c in self._chunks:
            if version and c.version != version:
                continue
            if source_type and c.source_type != source_type:
                continue
            tf = Counter(_tokens(c.text + " " + c.heading))
            score = sum(tf[t] * math.log(1 + n / (1 + df[t])) for t in q)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]