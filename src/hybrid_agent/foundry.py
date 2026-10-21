import logging

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, WebSearchTool, WebSearchToolFilters
from langchain_core.tools import tool

from configs.settings import FOUNDRY_PROJECT_ENDPOINT, FOUNDRY_MODEL_NAME
from src.hybrid_agent.prompts import RESEARCH_PROMPT

logger = logging.getLogger("hybrid_agent")

RESEARCH_AGENT = "research-agent"


# Connect to the Foundry project. Login comes from "az login" (no API key in the code).
project = AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=DefaultAzureCredential())
openai = project.get_openai_client()

# The Foundry agent: it searches the web by itself (built-in tool, run by Foundry). Each start saves a new version.
project.agents.create_version(
    agent_name=RESEARCH_AGENT,
    definition=PromptAgentDefinition(
        model=FOUNDRY_MODEL_NAME,
        instructions=RESEARCH_PROMPT,
        # tools=[WebSearchTool()],
        tools=[
            WebSearchTool(
                filters=WebSearchToolFilters(
                    allowed_domains=[
                        "insurancejournal.com",     # insurance industry news
                        "reinsurancene.ws",         # reinsurance news
                        "artemis.bm",               # reinsurance / cat bonds
                        "ofac.treasury.gov",        # US sanctions
                    ]
                )
            )
        ]
    ),
)


@tool
def ask_research_agent(question: str) -> str:
    """Ask the Foundry research agent, which searches the INTERNET for current information.

    Use this tool for anything that is not in our database or the weather API: recent news about a company
    (insured, cedant or broker), sanctions, natural disasters, regulations, or other public information.
    Input: question - one clear, complete question, e.g. "Recent news about Trisura Specialty Insurance Company".
    Returns: a short answer with the sources (web links) it used.
    """

    logger.info(f"[ask_research_agent] {question}")

    # One question in, one answer out. Foundry runs the web search itself, so no loop is needed here.
    response = openai.responses.create(
        input=question,
        extra_body={"agent_reference": {"name": RESEARCH_AGENT, "type": "agent_reference"}},
    )

    logger.info("[ask_research_agent] answered")
    return response.output_text
