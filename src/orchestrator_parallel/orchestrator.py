import sys
import json
import logging

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware

from src.orchestrator_parallel.llm import model
from src.orchestrator_parallel.prompts import ORCHESTRATOR_PROMPT
from src.orchestrator_parallel.agents import data_check_agent, history_agent, risk_agent

logger = logging.getLogger("orchestrator_parallel")


# The orchestrator calls all three agents in one step, then merges their answers.
orchestrator = create_agent(
    model=model,
    tools=[data_check_agent, history_agent, risk_agent],
    system_prompt=ORCHESTRATOR_PROMPT,
    # Each agent may run only once per review
    middleware=[
        ToolCallLimitMiddleware(tool_name="data_check_agent", run_limit=1),
        ToolCallLimitMiddleware(tool_name="history_agent", run_limit=1),
        ToolCallLimitMiddleware(tool_name="risk_agent", run_limit=1),
    ],
)


def review(submission_key: str) -> dict:

    logger.info(f"[orchestrator] reviewing submission {submission_key}")
    result = orchestrator.invoke({"messages": [{"role": "user", "content": f"Review submission {submission_key}"}]})
    logger.info("[orchestrator] finished")

    steps = []
    answers = {}

    for message in result["messages"]:

        # The agents the orchestrator called in one step
        if message.type == "ai" and message.tool_calls:
            steps.append([call["name"] for call in message.tool_calls])

        # Each agent's answer (keep the first one; a repeated call is blocked)
        if message.type == "tool" and message.name not in answers:
            answers[message.name] = message.text

    return {
        "steps": steps,
        "data_check": answers.get("data_check_agent", "not checked"),
        "history": answers.get("history_agent", "not checked"),
        "risk": answers.get("risk_agent", "not checked"),
        "review": result["messages"][-1].text,
    }


if __name__ == "__main__":

    # Show our logs in the terminal, as "time  message"
    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    result = review(sys.argv[1])
    print(json.dumps(result, indent=2))
