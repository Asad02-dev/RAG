import logging

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.tools import tool

from src.supervisor_parallel.llm import model
from src.supervisor_parallel.prompts import DATA_CHECK_PROMPT, HISTORY_PROMPT, RISK_PROMPT
from src.supervisor_parallel.tools import get_facts, get_history

logger = logging.getLogger("supervisor_parallel")


# Each agent may call its tool at most 2 times per review. A 3rd call is blocked,
# so the agent stops guessing (e.g. other spellings of a wrong number) and answers with what it found.
def two_tries():
    return ToolCallLimitMiddleware(run_limit=2)


# The three agents. Each one calls its own tool, then answers.
data_check = create_agent(model=model, tools=[get_facts], system_prompt=DATA_CHECK_PROMPT, middleware=[two_tries()])
history = create_agent(model=model, tools=[get_history], system_prompt=HISTORY_PROMPT, middleware=[two_tries()])
risk = create_agent(model=model, tools=[get_facts], system_prompt=RISK_PROMPT, middleware=[two_tries()])


def ask(agent, name: str, submission_key: str) -> str:
    logger.info(f"[{name}] started")
    result = agent.invoke({"messages": [{"role": "user", "content": f"Check submission {submission_key}"}]})
    logger.info(f"[{name}] finished")
    return result["messages"][-1].text


# The supervisor calls the agents through these tools.
# Calls made in the same step run at the same time.

@tool
def data_check_agent(submission_key: str) -> str:
    """Checks if the submission is complete."""
    return ask(data_check, "data_check", submission_key)


@tool
def history_agent(submission_key: str) -> str:
    """Checks for other submissions with the same insured, cedant or broker."""
    return ask(history, "history", submission_key)


@tool
def risk_agent(submission_key: str) -> str:
    """Checks how risky the submission is."""
    return ask(risk, "risk", submission_key)
