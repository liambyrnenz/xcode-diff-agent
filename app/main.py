from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.loop import Agent
from app.agent.tools import ToolRegistry
from app.api.routes import router
from app.config import get_settings
from app.facts.repo import FactsRepo
from app.llm.factory import build_llm_client
from app.retrieval.store import InMemoryKeywordStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    store = InMemoryKeywordStore(s.data_dir / "chunks.json")
    facts = FactsRepo(s.data_dir / "xcode_versions.json")
    app.state.agent = Agent(build_llm_client(s), ToolRegistry(store, facts), s.agent_max_steps)
    yield


app = FastAPI(title="Xcode Diff Agent", lifespan=lifespan)
app.include_router(router)