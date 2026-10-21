import sys
import sqlite3
import logging

from langchain.agents import create_agent
from langchain.agents.middleware import PIIMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver

from src.hybrid_agent.llm import model
from src.hybrid_agent.prompts import AGENT_PROMPT
from src.hybrid_agent.tools import get_weather, get_submission
from src.hybrid_agent.foundry import ask_research_agent

logger = logging.getLogger("hybrid_agent")

# The memory: every conversation is saved here, by thread_id
connection = sqlite3.connect("data/hybrid_agent.db", check_same_thread=False)


# Our LangGraph agent (the orchestrator). It decides which tool to call; one of them is the Foundry agent.
agent = create_agent(
    model=model,
    tools=[get_weather, get_submission, ask_research_agent],
    system_prompt=AGENT_PROMPT,
    checkpointer=SqliteSaver(connection),
)


def chat(thread_id: str, question: str) -> str:

    # Same thread_id = same conversation, so the agent remembers earlier messages
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(f"[agent] question: {question}")
    result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config)
    logger.info("[agent] answered")

    return result["messages"][-1].text

# To show the history on the Streamlit page
def history(thread_id: str) -> list:

    # All saved messages of this conversation
    config = {"configurable": {"thread_id": thread_id}}
    return agent.get_state(config).values.get("messages", [])


if __name__ == "__main__":

    # Show our logs in the terminal, as "time  message"
    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    # Print answers with symbols like °C correctly in the Windows terminal
    sys.stdout.reconfigure(encoding="utf-8")

    # python -m src.hybrid_agent.agent user-1 "What is the weather in Karachi?"
    print(chat(sys.argv[1], sys.argv[2]))
