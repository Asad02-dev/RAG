import sys
import sqlite3
import logging

import openai
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from src.orchestrator_agent.llm import model
from src.orchestrator_agent.prompts import AGENT_PROMPT
from src.orchestrator_agent.tools import get_weather, get_submission

logger = logging.getLogger("orchestrator_agent")

# The memory: every conversation is saved here, by thread_id
connection = sqlite3.connect("data/orchestrator_agent.db", check_same_thread=False)


# Safety net for tool errors we did not expect (the tools already handle the usual ones).
# The agent gets a short message instead of a crash, so the conversation keeps working:
# an unanswered tool call would break this conversation's memory for every next question.
@wrap_tool_call
def handle_tool_errors(request, handler):
    try:
        return handler(request)
    except Exception:
        name = request.tool_call["name"]
        logger.exception(f"[{name}] failed")   # full error details in the log
        return ToolMessage(
            content=f"The tool {name} failed. Tell the user this information is not available right now.",
            tool_call_id=request.tool_call["id"],
        )


# The agent decides by itself which tool to call, based on the user's question
agent = create_agent(
    model=model,
    tools=[get_weather, get_submission],
    system_prompt=AGENT_PROMPT,
    checkpointer=SqliteSaver(connection),
    middleware=[handle_tool_errors],
)


def chat(thread_id: str, question: str) -> str:

    # Same thread_id = same conversation, so the agent remembers earlier messages
    config = {"configurable": {"thread_id": thread_id}}

    logger.info(f"[agent] question: {question}")

    # If OpenAI fails, the user gets a short message; the details go to the log
    try:
        result = agent.invoke({"messages": [{"role": "user", "content": question}]}, config)

    except openai.AuthenticationError:
        logger.error("[agent] OpenAI rejected the API key")
        return "The AI service is not set up correctly (the OpenAI API key was rejected)."

    except openai.RateLimitError:
        logger.error("[agent] OpenAI rate limit or quota reached")
        return "The AI service is busy or its usage limit is reached. Please try again in a minute."

    except openai.APIConnectionError:
        # Also covers timeouts
        logger.error("[agent] cannot reach OpenAI")
        return "I can't reach the AI service right now. Please check the internet connection and try again."

    except openai.APIStatusError as error:
        logger.error(f"[agent] OpenAI error {error.status_code}: {error.message}")
        return "The AI service returned an error. Please try again."

    except Exception:
        # Anything else: keep the app running, and log the full error to fix it later
        logger.exception("[agent] unexpected error")
        return "Sorry, something went wrong while answering. Please try again."

    logger.info("[agent] answered")
    return result["messages"][-1].text


# To show the history on the Streamlit page
def history(thread_id: str) -> list:

    # All saved messages of this conversation
    config = {"configurable": {"thread_id": thread_id}}

    try:
        return agent.get_state(config).values.get("messages", [])

    except sqlite3.Error:
        # The memory file can't be read: show an empty conversation instead of crashing
        logger.exception("[agent] cannot read the conversation history")
        return []


if __name__ == "__main__":

    # python -m src.orchestrator_agent.agent user-1 "What is the weather in Karachi?"
    if len(sys.argv) != 3:
        print('Usage: python -m src.orchestrator_agent.agent <conversation-id> "<question>"')
        sys.exit(1)

    # Show our logs in the terminal, as "time  message"
    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    # Print answers with symbols like °C correctly in the Windows terminal
    sys.stdout.reconfigure(encoding="utf-8")

    print(chat(sys.argv[1], sys.argv[2]))
