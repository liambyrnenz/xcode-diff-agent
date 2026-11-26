# Xcode Diff Agent

A FastAPI service that answers questions about differences between Xcode versions, grounded in Apple's own documentation. It is aimed at questions like:

- Which iOS/macOS SDK features were added or removed between two versions?
- What Swift language changes and deprecations does a version bring?
- Which macOS versions can host a given Xcode?
- Which devices and deployment targets are supported?
- What toolchain and dependency differences exist?
- What behaviour changes should I expect when upgrading?

An LLM agent answers each question by calling tools over two data sources, then cites its sources:

1. **Document chunks**: Xcode release notes (`.md` downloads), Apple Developer news, OS release notes, and Swift Evolution / changelogs, chunked and searchable.
2. **Structured facts**: per-version data such as minimum macOS, Swift version, SDKs and deployment targets, ideally extracted from the [Xcode system requirements page](https://developer.apple.com/xcode/system-requirements/). Numeric and tabular answers come from here rather than from the model reading prose.

> **Status:** starter scaffold. It is not wired to real credentials or a production datastore, and the seed data and model IDs are placeholders. Verify them before relying on any output.

## Architecture

```
HTTP POST /ask
      │
      ▼
  FastAPI route ──► Agent loop ──► LLMClient (provider-neutral)
                       │                 ├─ AnthropicDirectClient   (Claude API)
                       │                 ├─ AnthropicVertexClient   (Claude on GCP Vertex AI)
                       │                 └─ GeminiVertexClient      (Gemini on GCP Vertex AI)
                       ▼
                  ToolRegistry
                   ├─ search_docs                ──► DocStore (chunks)
                   ├─ diff_availability          ──► FactsRepo + DocStore
                   └─ get_toolchain_requirements ──► FactsRepo
```

### Model abstraction

All model calls go through `LLMClient` (`app/llm/base.py`). The agent only uses provider-neutral types (`Message`, `ToolSpec`, `ToolCall`, `ToolResult`, `LLMResponse`). Each backend converts to and from its SDK's wire format. SDKs are imported lazily inside each client, so you only need the one you use installed.

| `LLM_PROVIDER` | Class | Notes |
|---|---|---|
| `anthropic` | `AnthropicDirectClient` | Uses `ANTHROPIC_API_KEY` |
| `anthropic_vertex` | `AnthropicVertexClient` | Claude via Vertex AI, using Application Default Credentials |
| `gemini_vertex` | `GeminiVertexClient` | Untested sketch that proves the abstraction fits a non-Anthropic message shape |

To add a provider, implement `LLMClient.complete()` and register it in `app/llm/factory.py`. Nothing else should import a model SDK.

### Agent tools

| Tool | Purpose | Backed by |
|---|---|---|
| `search_docs(query, version?, source_type?)` | Search release notes, news, OS notes and Swift Evolution | `DocStore` |
| `diff_availability(from_version, to_version)` | Structured diff (SDKs, min macOS, Swift, deployment targets) plus release-note passages on features, deprecations and behaviour changes | `FactsRepo` + `DocStore` |
| `get_toolchain_requirements(version)` | Host macOS, bundled Swift, SDKs and minimum deployment targets for one version | `FactsRepo` |

`get_adoption_share(version)` (OS version uptake) is deliberately **not implemented yet**; see the roadmap.

The system prompt (`app/agent/prompts.py`) tells the model to ground every claim in tool output, prefer structured tools for numbers, cite URLs, and state its assumptions when a version is ambiguous.

## Project layout

```
xcode-diff-agent/
├── pyproject.toml              # dependencies; optional extras per provider
├── .env.example                # copy to .env
├── README.md
├── app/
│   ├── main.py                 # FastAPI app; wires store, facts, LLM and agent in lifespan
│   ├── config.py               # pydantic-settings; all env config lives here
│   ├── api/
│   │   ├── routes.py           # GET /health, POST /ask
│   │   └── schemas.py          # request/response models
│   ├── llm/
│   │   ├── base.py             # LLMClient interface + neutral message/tool types
│   │   ├── anthropic_client.py # direct Claude + Claude-on-Vertex (shared Messages logic)
│   │   ├── gemini_vertex_client.py
│   │   └── factory.py          # picks a client from settings
│   ├── agent/
│   │   ├── loop.py             # tool-use loop, step limit, citation collection
│   │   ├── prompts.py          # system prompt
│   │   └── tools.py            # tool specs, handlers, registry
│   ├── retrieval/
│   │   └── store.py            # Chunk, DocStore protocol, in-memory keyword store
│   ├── facts/
│   │   └── repo.py             # structured per-version facts + diffing
│   └── ingestion/
│       ├── sources.py          # list of documents to ingest
│       └── pipeline.py         # fetch → chunk → store
├── scripts/
│   └── ingest.py               # CLI entry point for ingestion
├── data/
│   └── xcode_versions.json     # seed facts (placeholders; verify against Apple)
└── tests/
    └── test_agent_loop.py      # agent loop with a fake LLM
```

### Where things live

- **Swap the model provider:** set `LLM_PROVIDER`; add new ones in `app/llm/`.
- **Add a tool:** register it in `ToolRegistry._register_all()` in `app/agent/tools.py`.
- **Add a document source:** add a `Source` in `app/ingestion/sources.py`. Markdown works today; HTML sources need a parser in `pipeline.py`.
- **Change retrieval:** implement the `DocStore` protocol in `app/retrieval/store.py` and construct it in `app/main.py` and `scripts/ingest.py`.

## Configuration

Copy `.env.example` to `.env`.

| Variable | Description |
|---|---|
| `LLM_PROVIDER` | `anthropic`, `anthropic_vertex` or `gemini_vertex` |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Direct Claude API settings |
| `GCP_PROJECT`, `GCP_REGION` | Vertex AI project and region (auth via Application Default Credentials) |
| `VERTEX_CLAUDE_MODEL`, `VERTEX_GEMINI_MODEL` | Model IDs on Vertex; check Model Garden for what is available to you |
| `DATA_DIR` | Where chunks and facts live (default `./data`) |
| `AGENT_MAX_STEPS` | Max tool-use iterations per question |

## Running it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[anthropic,dev]"      # add ,gemini if using gemini_vertex
cp .env.example .env                   # fill in provider settings
python -m scripts.ingest               # (run from the project root)
uvicorn app.main:app --reload
curl -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"What changed between Xcode 16.4 and 26.0 for macOS compatibility?"}'
```

Run tests with `pytest`. The included test uses a fake `LLMClient`, so it needs no API keys.

## Known limitations

- Retrieval is an in-memory keyword scorer persisted to `data/chunks.json`. It is a stand-in, not production search.
- `data/xcode_versions.json` is hand-seeded with placeholder values. Ingestion should populate it from the system requirements page.
- `diff_availability` only pulls release-note passages for the target version. Changes in intermediate versions (e.g. 16.4 → 26.0 spanning several releases) are not yet collected.
- Tool calls within one agent step run sequentially.
- Markdown chunking splits on headings but does not retain the full heading path.
- The Gemini client is an untested sketch.

## Roadmap / TODO

**Next up**
- [ ] **Introduce uv to replace pip, venv, etc.** `uv` seems more used in production, so try this out.
- [ ] **Conversation history, streaming and auth.** `Agent.run` already accepts `history`, so multi-turn is mostly an API-layer change (session IDs, storage). Streaming means adding a streaming method to `LLMClient` and a StreamableHTTP endpoint - see `StreamingResponse`. Add authentication and rate limiting before exposing the service.
- [ ] **RAG configuration.** RAG in this project is best for searching from the documents but not necessarily comparing across them. Perhaps start with limiting the project to queries best suited for RAG, then move on to databases supporting querying for comparisons.
- [ ] **pgvector retrieval.** Replace `InMemoryKeywordStore` with a Postgres + pgvector implementation of `DocStore`. Aim for hybrid search (keyword + embeddings), with metadata filters on `version` and `source_type`, plus an embedding step in the ingestion pipeline. Keep the `DocStore` interface unchanged so the agent and tools don't need to change.
- [ ] **Introduce LangChain.** Incorporate LangChain in to replace the manual code for things like agent handling, state management, streaming, etc. Consider also LangGraph.

**Data and ingestion**
- [ ] Parse the system requirements page (HTML) into `xcode_versions.json`.
- [ ] Discover and ingest all Xcode release-note versions, not just one.
- [ ] Add Apple Developer news (RSS), OS release notes, and Swift Evolution proposals / CHANGELOG.
- [ ] Incremental ingestion (skip unchanged documents, content hashing).
- [ ] Keep the full heading path on chunks and preserve bullet lists.

**Agent**
- [ ] Cover intermediate versions in `diff_availability`.
- [ ] Run independent tool calls concurrently with `asyncio.gather`.
- [ ] Retry and backoff on model/API errors.
- [ ] Evaluation set of version-diff questions with expected answers.
- [ ] Agentic loop via framework like LangChain.

**Deferred**
- [ ] `get_adoption_share(version)`: OS version uptake data relevant to an Xcode version's SDK. Needs a data source before the tool is added.

**Productionising**
- This client shouldn't really be responsible for handling LLM usage, that should be the responsibility of the cloud provider. As such, maybe the direct Anthropic SDK route can be removed.
- OpenTelemetry or something similar for costs.
- Structured logging, request IDs, error-handling middleware, API-key auth between the app and backend, and a test suite that mocks the Anthropic client. (Check what of this exists first.)