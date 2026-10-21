import os
import sys
import json
import logging

from src.foundry_agent.client import openai, AGENT_NAME
from src.foundry_agent.tools import FUNCTIONS

logger = logging.getLogger("foundry_agent")

# Our Conversation ID (e.g. "user-1") -> Foundry's conversation ID. Foundry keeps the messages themselves.
CONVERSATIONS_FILE = "data/foundry_conversations.json"


# The agent already exists in Foundry (create_agent.py creates it).
# Every request goes to it by its name, and Foundry uses its latest version.
AGENT = {"agent_reference": {"name": AGENT_NAME, "type": "agent_reference"}}


def conversation(thread_id: str) -> str:

    # Find this user's Foundry conversation, or create a new one
    saved = json.load(open(CONVERSATIONS_FILE)) if os.path.exists(CONVERSATIONS_FILE) else {}

    if thread_id not in saved:
        saved[thread_id] = openai.conversations.create().id
        json.dump(saved, open(CONVERSATIONS_FILE, "w"), indent=2)

    return saved[thread_id]


def chat(thread_id: str, question: str) -> str:

    conversation_id = conversation(thread_id)
    logger.info(f"[agent] question: {question}")

    # Foundry runs the agent and saves the messages in the conversation (that is the memory)
    response = openai.responses.create(conversation=conversation_id, input=question, extra_body=AGENT)

    # While the agent asks for tools: run them here and send the results back
    while any(item.type == "function_call" for item in response.output):

        results = []
        for item in response.output:
            if item.type == "function_call":
                output = FUNCTIONS[item.name](**json.loads(item.arguments))
                results.append({"type": "function_call_output", "call_id": item.call_id, "output": output})

        response = openai.responses.create(conversation=conversation_id, input=results, extra_body=AGENT)

    logger.info("[agent] answered")
    return response.output_text


def history(thread_id: str) -> list:

    # All saved messages of this conversation, oldest first, as {"role": ..., "text": ...}
    items = openai.conversations.items.list(conversation(thread_id), order="asc")

    return [
        {"role": item.role, "text": "".join(part.text for part in item.content if hasattr(part, "text"))}
        for item in items
        if item.type == "message"
    ]


if __name__ == "__main__":

    # Show our logs in the terminal, as "time  message"
    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    # Print answers with symbols like °C correctly in the Windows terminal
    sys.stdout.reconfigure(encoding="utf-8")

    # python -m src.foundry_agent.agent user-1 "What is the weather in Karachi?"
    print(chat(sys.argv[1], sys.argv[2]))
