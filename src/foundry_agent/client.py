from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

from configs.settings import FOUNDRY_PROJECT_ENDPOINT


# Connect to the Foundry project. Login comes from "az login" (no API key in the code).
project = AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=DefaultAzureCredential())

# The client that talks to the agent: conversations (the memory) and responses (the answers)
openai = project.get_openai_client()

# The agent's name in Foundry. create_agent.py creates it, agent.py uses it.
AGENT_NAME = "orchestrator-agent"
