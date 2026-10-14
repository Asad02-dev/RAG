import logging

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware

from src.supervisor_parallel.llm import model
from src.supervisor_parallel.prompts import DATA_CHECK_PROMPT, HISTORY_PROMPT, RISK_PROMPT
from src.supervisor_parallel.tools import get_facts, get_history

logger = logging.getLogger("supervisor_parallel")


# Logs when an agent starts and finishes
class Log(AgentMiddleware):

    def __init__(self, agent: str):
        super().__init__()
        self.agent = agent

    def before_agent(self, state, runtime):
        logger.info(f"[{self.agent}] started")

    def after_agent(self, state, runtime):
        logger.info(f"[{self.agent}] finished")


# The three agents the supervisor manages. Each one calls its own tool, then answers.
data_check_agent = create_agent(
    model=model,
    tools=[get_facts],
    system_prompt=DATA_CHECK_PROMPT,
    name="data_check_agent",
    middleware=[Log("data_check")],
)

history_agent = create_agent(
    model=model,
    tools=[get_history],
    system_prompt=HISTORY_PROMPT,
    name="history_agent",
    middleware=[Log("history")],
)

risk_agent = create_agent(
    model=model,
    tools=[get_facts],
    system_prompt=RISK_PROMPT,
    name="risk_agent",
    middleware=[Log("risk")],
)
