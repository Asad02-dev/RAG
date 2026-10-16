from fastapi import APIRouter
from agents import Runner, SQLiteSession

from src.agent.agent import agent
from src.api.models import ChatRequest, ChatResponse

router = APIRouter()

DATABASE_PATH = "data/conversations.db"


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session = SQLiteSession(
        request.session_id,
        DATABASE_PATH,
    )

    result = await Runner.run(
        agent,
        request.message,
        session=session,
    )

    return ChatResponse(
        session_id=request.session_id,
        response=result.final_output,
    )