# The agent as a web API (FastAPI). Start it from the project folder:
#   uvicorn src.mcp_agent.api:app --port 8001
# (Don't add --reload on Windows: with it, the API can't start the MCP server in the background.)
# Then start the Streamlit page in a second terminal. Try the API in the browser: http://localhost:8001/docs

import io
import sys
import logging

from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

from src.mcp_agent.agent import chat, history

# Show our logs in this terminal too, as "time  message"
logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("mcp_agent")
logger.setLevel(logging.INFO)

app = FastAPI(title="MCP Agent")


# What Streamlit sends to /chat
class Question(BaseModel):
    thread_id: str
    question: str


@app.post("/chat")
async def ask_question(body: Question) -> dict:

    # Collect the agent's log lines for this question, to show them in Streamlit's "Logs" box.
    # (If two people ask at the same moment, their log lines can mix. Fine for a POC.)
    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)

    try:
        # FastAPI runs async code itself, so we can simply await the agent
        answer = await chat(body.thread_id, body.question)
    finally:
        logger.removeHandler(handler)

    return {"answer": answer, "logs": logs.getvalue()}


@app.get("/history")
async def show_history(thread_id: str) -> list:

    # Only what the page needs: who wrote the message ("human" or "ai") and its text
    return [{"type": message.type, "text": message.text} for message in await history(thread_id)]
