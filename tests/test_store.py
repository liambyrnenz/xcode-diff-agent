import shutil
from pathlib import Path

import pytest

from app.retrieval.store import Chunk, InMemoryKeywordStore

FIXTURE = Path(__file__).parent / "fixtures" / "mock_chunks.json"


@pytest.fixture
def store(tmp_path):
    # Copy so add() (which rewrites the file) never touches the fixture.
    path = tmp_path / "chunks.json"
    shutil.copy(FIXTURE, path)
    return InMemoryKeywordStore(path)


def ids(chunks):
    return [c.id for c in chunks]


def test_ranks_by_term_frequency(store):
    hits = store.search("legacy build system")
    # The 26.0 chunk repeats "legacy" and "build", so it outranks the 16.4 one.
    assert ids(hits)[:2] == ["mock-26-deprecations", "mock-164-deprecations"]


def test_version_filter(store):
    hits = store.search("legacy build system", version="16.4")
    assert hits and all(c.version == "16.4" for c in hits)
    assert hits[0].id == "mock-164-deprecations"


def test_source_type_filter(store):
    hits = store.search("requires macOS", source_type="system_requirements")
    assert set(ids(hits)) == {"mock-26-sysreq", "mock-164-sysreq"}


def test_combined_filters(store):
    hits = store.search("requires macOS", version="16.4", source_type="system_requirements")
    assert ids(hits) == ["mock-164-sysreq"]


def test_version_filter_excludes_version_agnostic_docs(store):
    # News/Swift Evolution chunks have version=None, so any version filter drops them.
    assert "mock-news-26" in ids(store.search("announced available"))
    assert store.search("announced available", version="26.0") == []


def test_no_stemming(store):
    # "deprecated" and "deprecates" appear in the data, but exact-token matching
    # means "deprecate" matches nothing. This is a limit of the keyword store.
    assert store.search("deprecate") == []
    assert store.search("deprecated")


def test_k_limits_results(store):
    assert len(store.search("mock", k=3)) == 3


def test_add_persists_to_disk(store, tmp_path):
    store.add([Chunk("new-1", "freshly added zebra chunk", "Extra", "26.0",
                     "news", "https://example.com/zebra")])
    reloaded = InMemoryKeywordStore(tmp_path / "chunks.json")
    assert ids(reloaded.search("zebra")) == ["new-1"]