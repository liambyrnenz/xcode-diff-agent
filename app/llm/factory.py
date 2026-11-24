from app.config import Settings

from .base import LLMClient


def build_llm_client(s: Settings) -> LLMClient:
    match s.llm_provider:
        case "anthropic":
            from .anthropic_client import AnthropicDirectClient
            return AnthropicDirectClient(api_key=s.anthropic_api_key or "", model=s.anthropic_model)
        case "anthropic_vertex":
            from .anthropic_client import AnthropicVertexClient
            return AnthropicVertexClient(s.gcp_project or "", s.gcp_region, s.vertex_claude_model)
        case "gemini_vertex":
            from .gemini_vertex_client import GeminiVertexClient
            return GeminiVertexClient(s.gcp_project or "", s.gcp_region, s.vertex_gemini_model)
    raise ValueError(f"Unknown provider: {s.llm_provider}")