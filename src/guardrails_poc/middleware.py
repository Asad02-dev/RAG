import re
import logging

from langchain.agents.middleware import PIIMiddleware, before_agent, HumanInTheLoopMiddleware
from langchain_core.messages import AIMessage

logger = logging.getLogger("guardrails_poc")


# ── 1. PII: hide personal data ──

# Emails: hidden in the user's question AND in tool results (the Neo4j contacts have emails),
# so they never reach the LLM or the answer
hide_emails = PIIMiddleware("email", strategy="redact", apply_to_input=True, apply_to_tool_results=True)

# Credit card numbers typed by the user: only the last 4 digits are kept
hide_cards = PIIMiddleware("credit_card", strategy="mask", apply_to_input=True)


# ── 2. Block requests to change the database ──

# A "change" word together with a "database" word, e.g. "please add this into the db"
CHANGE_WORDS = r"\b(add|insert|create|update|edit|change|modify|delete|remove|drop|save|store|write)\b"
DB_WORDS = r"\b(db|database|neo4j|record|records|table|graph)\b"


@before_agent(can_jump_to=["end"])
def block_db_changes(state, runtime):

    question = state["messages"][-1].text.lower()

    if re.search(CHANGE_WORDS, question) and re.search(DB_WORDS, question):
        logger.info("[block_db_changes] blocked a request to change the database")
        # Answer right away and stop: the LLM is not called
        return {
            "messages": [AIMessage("Sorry, I can only read data. I can't add, change or delete anything in the database.")],
            "jump_to": "end",
        }


# ── 3. Human in the loop: a person must approve before submission data is read ──

# The agent pauses before get_submission runs. A person then approves (the tool runs)
# or rejects (the tool does not run, and the agent is told so). get_weather is not paused.
ask_approval = HumanInTheLoopMiddleware(
    interrupt_on={
        "get_submission": {
            "allowed_decisions": ["approve", "reject"],
            "description": "The agent wants to read confidential submission data from Neo4j.",
        },
    },
)
