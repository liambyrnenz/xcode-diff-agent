# from pathlib import Path
# from app.retrieval.store import InMemoryKeywordStore

# store = InMemoryKeywordStore(Path("tests/fixtures/mock_chunks.json"))
# for q, kw in [("legacy build system", {}),
#               ("legacy build system", {"version": "16.4"}),
#               ("requires macOS", {"source_type": "system_requirements"})]:
#     print(f"\n{q!r} {kw}")
#     for c in store.search(q, **kw):
#         print(f"  {c.id:24} v={c.version!s:5} {c.source_type:20} {c.heading}")