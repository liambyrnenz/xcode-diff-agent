# Roadmap

The path from the starter scaffold to a deployable service: get a first local run working, establish local document storage, build proper RAG and querying, then explore deployment.

Findings below are as of 2026-11-27. API and model details come from Anthropic's API reference. Nothing here has been tested against a live model.

## Phase 0: Fix before the first run

- [ ] **Fix the Claude call.** `app/llm/anthropic_client.py` passes `temperature=0.0`, which the installed `anthropic` 2.14.0 doesn't accept. Both Claude clients fail with `TypeError: AsyncMessages.create() got an unexpected keyword argument 'temperature'` before sending a request. Remove the argument from the request. The existing tests use a fake `LLMClient`, so add a test that runs the real client against a mocked connection.
- [ ] **Replace the default Vertex model** (urgent if using Vertex). The API reference lists Claude Sonnet 4.5 as retiring on 2026-11-30. Vertex's own schedule hasn't been checked. The ID is in `app/config.py` and `.env.example`.
- [ ] **Check the rest of the tool loop against Claude Sonnet 5.5.** Found by reading the code and API reference:
  - The client drops `thinking` blocks, which should be sent back unchanged.
  - The 2,048 `max_tokens` limit has to cover thinking as well as the answer.
  - The agent doesn't handle cut-off (`max_tokens`) or refused responses.

## Phase 1: First local run, then local document storage

**Before the first ingestion:** add `data/chunks.json` to `.gitignore`, and don't run ingestion twice until duplicates are fixed.

- [ ] **First end-to-end run.** Run ingestion, start the server, check `/health`, then ask a few questions. Start with the direct Anthropic API, which only needs a key in `.env` (calls are billed). The Vertex routes also need Google Cloud credentials.
- [ ] **Make local storage safe to rerun.**
  - Adding the same chunks again duplicates them (87 became 174 in testing), and one search can then return the same chunk twice.
  - Add `data/chunks.json` to `.gitignore`.
  - Have the store create its parent folder if missing, as the ingest script doesn't.
- [ ] **Incremental ingestion.** Skip unchanged documents using content hashes.
- [ ] **Clean up chunking.** The configured Apple release-notes URL returns Markdown and produced 87 chunks.
  - The first chunk contains hidden page metadata (an HTML comment).
  - 7 chunks exceed the 2,000-character target (largest: 5,394), because long paragraphs aren't split.
  - Keep the full heading path on chunks (42 are headed just "Resolved Issues") and preserve bullet lists.
- [ ] **Handle version names.** Searching version `26` finds nothing because chunks are stored as `26.0`. The facts lookup also needs an exact match.
- [ ] **Add a second release.** Only 26.0 is ingested, so comparisons have no 16.4 passages.
- [ ] **Verify the seed facts** in `data/xcode_versions.json`, which are placeholders. The 26.0 release notes agree on minimum macOS 15.6 and Swift 6.2; other values haven't been checked.
- [ ] **Hide `get_adoption_share` from the model.** It's deliberately not implemented, but is still offered as a tool that only returns an error.

## Phase 2: RAG and querying

- [ ] **Build an evaluation set first.** Version-diff questions with expected answers and expected sources, so search can be scored separately from the model. Record how keyword search does before changing it.
- [ ] **RAG configuration.** RAG suits searching the documents, but not necessarily comparing across them. Decide which queries go to search and which go to structured queries: structured data for comparisons, RAG for explanations. Consider limiting the project to queries suited to RAG first, then move on to databases that support comparison queries.
  - In testing, searching "behavior change" returned only "New Features" and "Resolved Issues" chunks.
  - The `diff_availability` result for 16.4 → 26.0 was about 16,000 characters with only the 26.0 notes loaded.
- [ ] **pgvector retrieval.** Replace `InMemoryKeywordStore` with a Postgres + pgvector implementation of `DocStore`, starting with a local database. Add storage and metadata filters (`version`, `source_type`) first, then an embedding step in ingestion and hybrid search (keyword + embeddings), checking each step against the evaluation set. Keep the `DocStore` interface unchanged so the agent and tools don't need to change. Needs an embedding model choice.
- [ ] **Expand the data.**
  - Parse the system requirements page (HTML) into `xcode_versions.json`.
  - Discover and ingest all Xcode release-note versions.
  - Add Apple Developer news (RSS), OS release notes, and Swift Evolution proposals / CHANGELOG.
- [ ] **Cover intermediate versions** in `diff_availability`.
- [ ] **Introduce LangChain.** Replace the manual code for agent handling (the agentic loop), state management, streaming, etc. Consider also LangGraph. Wait for a working baseline and evaluation set, so the two can be compared fairly.

## Phase 3: Deployment

### Reliability and observability

Check what of this exists first.

- [ ] **Make failures visible and recoverable.** Structured logging, request IDs and error-handling middleware. Include failed tool calls in `tool_trace`.
- [ ] **Retry and backoff** on model/API errors. The Anthropic SDK already retries some errors itself.
- [ ] **Cost tracking** with OpenTelemetry or something similar.
- [ ] **Run independent tool calls concurrently** with `asyncio.gather`.
- [ ] **Test suite that mocks the Anthropic client**, building on the Phase 0 test.

### Preparing to deploy

- [ ] **CI** for tests and lint, after fixing the 7 existing Ruff findings.
- [ ] **Container build.**
- [ ] **Choose a host and managed database,** and decide how to handle secrets and run ingestion. GCP would fit the existing Vertex support.
- [ ] **Reconsider the direct Anthropic SDK route.** This client shouldn't really be responsible for handling LLM usage; that should be the cloud provider's job. The direct route could be removed.

### Before exposing the service

- [ ] **Authentication and rate limiting,** including API-key auth between the app and backend.
- [ ] **Input limits.**

### When needed

- [ ] **Conversation history and streaming.** `Agent.run` already accepts `history`, so multi-turn is mostly an API-layer change (session IDs, storage). Streaming means adding a streaming method to `LLMClient` and a StreamableHTTP endpoint (see `StreamingResponse`).

## Deferred

- [ ] **`get_adoption_share(version)`:** OS version uptake data relevant to an Xcode version's SDK. Needs a data source before the tool is added back.

## Done

- [x] **Introduce uv** to replace pip, venv, etc.
