import sys
import asyncio
import logging

from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.mcp_agent.llm import model
from src.mcp_agent.prompts import AGENT_PROMPT

logger = logging.getLogger("mcp_agent")

# The memory: every conversation is saved here, by thread_id
MEMORY_FILE = "data/mcp_agent.db"


# How to reach our MCP server: start "python -m src.mcp_agent.mcp_server" in the background
# and talk to it through its input and output ("stdio")
mcp_client = MultiServerMCPClient({
    "tools": {
        "command": sys.executable,                    # the same Python that runs this file
        "args": ["-m", "src.mcp_agent.mcp_server"],
        "transport": "stdio",
    },
})

# The MCP server's tools (get_weather, get_submission), loaded the first time they are needed.
# They work like normal LangChain tools, but each call goes to the MCP server.
tools = []


async def load_tools():
    # Ask the MCP server for its tools, only once
    if not tools:
        tools.extend(await mcp_client.get_tools())


# Log every tool call: the tool runs in the MCP server, so we log its name and inputs here
@wrap_tool_call
async def log_tools(request, handler):
    logger.info(f"[tool] {request.tool_call['name']} {request.tool_call['args']}")
    result = await handler(request)        # the MCP server runs the tool
    logger.info(f"[tool] {request.tool_call['name']} done")
    return result


# MCP tools only work with "async" code, so the agent is called with ainvoke and await.
# The API (api.py) calls these functions; FastAPI runs the async code for us.
async def chat(thread_id: str, question: str) -> str:

    logger.info(f"[agent] question: {question}")
    await load_tools()

    # Same thread_id = same conversation, so the agent remembers earlier messages
    config = {"configurable": {"thread_id": thread_id}}

    async with AsyncSqliteSaver.from_conn_string(MEMORY_FILE) as memory:

        # The agent decides by itself which tool to call, based on the user's question
        agent = create_agent(model=model, tools=tools, system_prompt=AGENT_PROMPT, checkpointer=memory,
                             middleware=[log_tools])

        result = await agent.ainvoke({"messages": [{"role": "user", "content": question}]}, config)

    logger.info("[agent] answered")
    return result["messages"][-1].text


# To show the history on the Streamlit page
async def history(thread_id: str) -> list:

    await load_tools()
    config = {"configurable": {"thread_id": thread_id}}

    async with AsyncSqliteSaver.from_conn_string(MEMORY_FILE) as memory:
        agent = create_agent(model=model, tools=tools, system_prompt=AGENT_PROMPT, checkpointer=memory,
                             middleware=[log_tools])
        state = await agent.aget_state(config)

    # All saved messages of this conversation
    return state.values.get("messages", [])


if __name__ == "__main__":

    # Show our logs in the terminal, as "time  message"
    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    # Print answers with symbols like °C correctly in the Windows terminal
    sys.stdout.reconfigure(encoding="utf-8")

    # python -m src.mcp_agent.agent user-1 "What is the weather in Karachi?"
    # asyncio.run starts the async code from normal code (once, for this one question)
    print(asyncio.run(chat(sys.argv[1], sys.argv[2])))
