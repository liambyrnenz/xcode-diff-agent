from __future__ import annotations

import hashlib
import re

import httpx

from app.retrieval.store import Chunk, DocStore

from .sources import Source

_HEADING = re.compile(r"^(#{1,4})\s+(.*)$", re.M)


def chunk_markdown(md: str, src: Source, max_chars: int = 2000) -> list[Chunk]:
    """Split on headings, then on paragraph boundaries if a section is too long.
    TODO: carry the full heading path (H1 > H2 > H3) and keep bullet lists intact."""
    sections, last, heading = [], 0, "Introduction"
    for m in _HEADING.finditer(md):
        sections.append((heading, md[last:m.start()]))
        heading, last = m.group(2).strip(), m.end()
    sections.append((heading, md[last:]))

    chunks: list[Chunk] = []
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        buf = ""
        for para in body.split("\n\n"):
            if len(buf) + len(para) > max_chars and buf:
                chunks.append(_mk(buf, heading, src))
                buf = ""
            buf += para + "\n\n"
        if buf.strip():
            chunks.append(_mk(buf, heading, src))
    return chunks


def _mk(text: str, heading: str, src: Source) -> Chunk:
    cid = hashlib.sha1(f"{src.url}|{heading}|{text[:80]}".encode()).hexdigest()[:16]
    return Chunk(cid, text.strip(), heading, src.version, src.source_type, src.url)


async def ingest(sources: list[Source], store: DocStore) -> int:
    total = 0
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
        for src in sources:
            r = await http.get(src.url)
            r.raise_for_status()
            # TODO: HTML sources need parsing (selectolax/bs4); md sources go straight through.
            chunks = chunk_markdown(r.text, src)
            store.add(chunks)
            total += len(chunks)
    return total