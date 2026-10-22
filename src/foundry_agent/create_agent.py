# Create (or update) the agent in Foundry: model, instructions and tools.
# Run it once, and again every time you change prompts.py or the tool descriptions in tools.py:
#   python -m src.foundry_agent.create_agent
# Each run saves a new version of the agent; the chat (agent.py) always uses the latest one.

import sys

from azure.ai.projects.models import PromptAgentDefinition

sys.path.insert(0, ".")   # so the "src..." and "configs..." imports work

from configs.settings import FOUNDRY_MODEL_NAME
from src.foundry_agent.client import project, AGENT_NAME
from src.foundry_agent.prompts import AGENT_PROMPT
from src.foundry_agent.tools import weather_tool, submission_tool


if __name__ == "__main__":

    agent = project.agents.create_version(
        agent_name=AGENT_NAME,
        definition=PromptAgentDefinition(
            model=FOUNDRY_MODEL_NAME,
            instructions=AGENT_PROMPT,
            tools=[weather_tool, submission_tool],
        ),
    )

    print(f"Agent '{agent.name}' saved in Foundry, version {agent.version}")
