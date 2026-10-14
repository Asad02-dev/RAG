import sys
import json
import logging

from langgraph_supervisor import create_supervisor

from src.supervisor_parallel.llm import model
from src.supervisor_parallel.prompts import SUPERVISOR_PROMPT
from src.supervisor_parallel.agents import data_check_agent, history_agent, risk_agent

logger = logging.getLogger("supervisor_parallel")


# The built-in LangGraph supervisor: hands off to the three agents, then merges their answers
supervisor = create_supervisor(
    agents=[data_check_agent, history_agent, risk_agent],
    model=model,
    prompt=SUPERVISOR_PROMPT,
    # Don't add "Transferring back to supervisor" messages after every agent
    add_handoff_back_messages=False,
    # parallel_tool_calls=True,
    # Write the agent's name into each message, so the supervisor knows who answered
    include_agent_name="inline",
).compile()


def review(submission_key: str) -> dict:

    logger.info(f"[supervisor] reviewing submission {submission_key}")
    result = supervisor.invoke(
        {"messages": [{"role": "user", "content": f"Review submission {submission_key}"}]},
        # Safety limit, in case the supervisor keeps handing off
        {"recursion_limit": 30},
    )
    logger.info("[supervisor] finished")

    answers = {}

    for message in result["messages"]:

        # Each agent's answer (keep the first one)
        if message.type == "ai" and message.name in ("data_check_agent", "history_agent", "risk_agent"):
            answers.setdefault(message.name, message.text)

    return {
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
