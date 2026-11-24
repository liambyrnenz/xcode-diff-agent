from fastapi import APIRouter, Request

from .schemas import AskRequest, AskResponse

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request):
    result = await request.app.state.agent.run(body.question)
    return AskResponse(answer=result.answer, citations=result.citations,
                       tool_trace=result.tool_trace, steps=result.steps)