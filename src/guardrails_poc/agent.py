import sys
import sqlite3
import logging

from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from src.guardrails_poc.llm import model
from src.guardrails_poc.prompts import AGENT_PROMPT
from src.guardrails_poc.tools import get_weather, get_submission
from src.guardrails_poc.middleware import hide_emails, hide_cards, block_db_changes, ask_approval

logger = logging.getLogger("guardrails_poc")

# The memory: every conversation is saved here, by thread_id.
# It also saves a paused agent, so it can wait for approval (even after a restart).
connection = sqlite3.connect("data/guardrails_poc.db", check_same_thread=False)


# The agent decides by itself which tool to call, based on the user's question
agent = create_agent(
    model=model,
    tools=[get_weather, get_submission],
    system_prompt=AGENT_PROMPT,
    checkpointer=SqliteSaver(connection),
    # Guardrails: block database changes, hide emails and card numbers, ask a person before reading a submission
    middleware=[block_db_changes, hide_emails, hide_cards, ask_approval],
)


def chat(thread_id: str, question: str) -> str | None:

    # Same thread_id = same conversation, so the agent remembers earlier messages
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(f"[agent] question: {question}")
    result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config)

    return answer(result)


def pending(thread_id: str) -> list:

    # The tool calls waiting for approval, e.g. [{"name": "get_submission", "args": {...}, "description": ...}]
    config = {"configurable": {"thread_id": thread_id}}
    return [request for item in agent.get_state(config).interrupts for request in item.value["action_requests"]]


def decide(thread_id: str, approve: bool) -> str | None:

    # Continue the paused agent with the person's decision (one decision per waiting tool call)
    config = {"configurable": {"thread_id": thread_id}}

    if approve:
        decision = {"type": "approve"}
    else:
        decision = {"type": "reject", "message": "The user did not approve reading the submission data."}

    logger.info(f"[human] {decision['type']}")
    result = agent.invoke(Command(resume={"decisions": [decision] * len(pending(thread_id))}), config)

    return answer(result)


def answer(result: dict) -> str | None:

    # None = the agent is paused and waits for approval
    if "__interrupt__" in result:
        logger.info("[agent] waiting for approval")
        return None

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

    # python -m src.guardrails_poc.agent user-1 "Who is the broker of submission 1547612?"
    reply = chat(sys.argv[1], sys.argv[2])

    # While the agent waits for approval, ask the person in the terminal
    while reply is None:
        for request in pending(sys.argv[1]):
            print(f"\nApproval needed: {request['name']}({request['args']})")
        reply = decide(sys.argv[1], input("Approve? (y/n): ").strip().lower() == "y")

    print(reply)
