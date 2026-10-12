from langchain.agents import create_agent

from src.supervisor_langgraph.llm import model
from src.supervisor_langgraph.prompts import TA_PROMPT, UW_PROMPT
from src.supervisor_langgraph.tools import get_facts


# TA Agent: decides by itself when to call get_facts (Neo4j)
ta_agent = create_agent(
    model=model,
    tools=[get_facts],
    system_prompt=TA_PROMPT,
    name="ta_agent",
)


# Underwriter Agent: no tools, it only reasons over the conversation
uw_agent = create_agent(
    model=model,
    tools=[],
    system_prompt=UW_PROMPT,
    name="uw_agent",
)
