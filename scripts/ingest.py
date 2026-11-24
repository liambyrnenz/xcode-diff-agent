import asyncio

from app.config import get_settings
from app.ingestion.pipeline import ingest
from app.ingestion.sources import SOURCES
from app.retrieval.store import InMemoryKeywordStore


async def main():
    s = get_settings()
    store = InMemoryKeywordStore(s.data_dir / "chunks.json")
    n = await ingest(SOURCES, store)
    print(f"Ingested {n} chunks")


asyncio.run(main())