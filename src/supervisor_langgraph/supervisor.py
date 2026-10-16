import sys
import sqlite3

from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.sqlite import SqliteSaver

from src.supervisor_langgraph.llm import model
from src.supervisor_langgraph.prompts import SUPERVISOR_PROMPT
from src.supervisor_langgraph.agents import ta_agent, uw_agent
from src.services.neo4j_service import driver


# Every case's state is saved in this file, so it survives restarts
DATABASE_PATH = "data/supervisor_cases.db"

# Safety limit for the number of steps in one user message
MAX_STEPS = 30


# ── 1. Supervisor: the prebuilt LangGraph supervisor manages both agents ──

def build_supervisor():

    supervisor = create_supervisor(
        agents=[ta_agent, uw_agent],
        model=model,
        prompt=SUPERVISOR_PROMPT,
        # Don't add "Transferring back to supervisor" messages after every agent
        add_handoff_back_messages=False,
        # Write the agent's name into each message, so every agent knows who said what
        include_agent_name="inline",
    )

    # SqliteSaver saves every case's state to DATABASE_PATH, by thread_id
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)

    return supervisor.compile(checkpointer=SqliteSaver(connection))


app = build_supervisor()


# ── 2. Entry point: send a user message into a case ──

def chat(case_id: str, text: str) -> list:

    # Same case_id = same thread = the conversation continues
    config = {
        "configurable": {"thread_id": case_id},
        "recursion_limit": MAX_STEPS,
    }

    old_count = len(app.get_state(config).values.get("messages", []))

    result = app.invoke(
        {"messages": [{"role": "user", "content": text}]},
        config,
    )

    # Return only the messages created for this user message
    return result["messages"][old_count:]


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print('Usage: python -m src.supervisor_langgraph.supervisor <case_id> "<message>"')
        print('Example: python -m src.supervisor_langgraph.supervisor case-1547612 "Should we quote submission 1547612?"')
        sys.exit(1)

    case_id, text = sys.argv[1], sys.argv[2]

    for message in chat(case_id, text):

        # Who wrote it: the user, the supervisor, an agent or a tool
        sender = message.name or message.type

        # A message that calls a tool (e.g. "transfer_to_ta_agent" or "get_facts")
        for call in getattr(message, "tool_calls", []):
            print(f"[{sender}] -> calls {call['name']}\n")

        # message.text is always plain text (content can be a list of parts)
        if message.text and message.type != "tool":
            print(f"[{sender}] {message.text}\n")

    driver.close()
