import sys
import json
import logging

from langgraph_supervisor import create_supervisor

from src.supervisor_parallel.llm import model
from src.supervisor_parallel.prompts import SUPERVISOR_PROMPT
from src.supervisor_parallel.agents import data_check_agent, history_agent, risk_agent

logger = logging.getLogger("supervisor_parallel")


# The built-in LangGraph supervisor, with the three agents given as tools (not hand-offs).
# Hand-offs can't run in parallel, but tool calls made in one step run at the same time.
supervisor = create_supervisor(
    agents=[],
    tools=[data_check_agent, history_agent, risk_agent],
    model=model,
    prompt=SUPERVISOR_PROMPT,
    # The supervisor may call several tools (agents) in one step
    parallel_tool_calls=True,
).compile()


def review(submission_key: str) -> dict:

    logger.info(f"[supervisor] reviewing submission {submission_key}")
    result = supervisor.invoke(
        {"messages": [{"role": "user", "content": f"Review submission {submission_key}"}]},
        # Safety limit, in case the supervisor keeps calling agents
        {"recursion_limit": 30},
    )
    logger.info("[supervisor] finished")

    steps = []
    answers = {}

    for message in result["messages"]:

        # The agents the supervisor called in one step
        if message.type == "ai" and message.tool_calls:
            steps.append([call["name"] for call in message.tool_calls])

        # Each agent's answer (keep the first one)
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
