import sys
import json
import logging

from langgraph_supervisor import create_supervisor
from langgraph.errors import GraphRecursionError

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


# Steps for at most 2 rounds of calling the agents. One round = 2 steps (the supervisor decides,
# the agents run), plus the final review. If the supervisor wants more (e.g. it keeps looking for
# a wrong submission number), it is stopped and we answer with STOPPED_REVIEW.
MAX_STEPS = 6

STOPPED_REVIEW = """RECOMMENDATION: NEED MORE INFO
REASON: The agents could not find the data needed after 2 tries. Please check the submission number."""


def review(submission_key: str) -> dict:

    logger.info(f"[supervisor] reviewing submission {submission_key}")

    try:
        result = supervisor.invoke(
            {"messages": [{"role": "user", "content": f"Review submission {submission_key}"}]},
            {"recursion_limit": MAX_STEPS},
        )
        messages = result["messages"]
        final_review = messages[-1].text

        # When the steps run out, the supervisor itself answers "Sorry, need more steps ..."
        if final_review.startswith("Sorry, need more steps"): # langgraph/prebuilt/chat_agent_executor.py, around line 684
            final_review = STOPPED_REVIEW
            logger.info("[supervisor] stopped after 2 tries")
        else:
            logger.info("[supervisor] finished")

    except GraphRecursionError:
        # The other way the step limit can end the review
        messages = []
        final_review = STOPPED_REVIEW
        logger.info("[supervisor] stopped after 2 tries")

    steps = []
    answers = {}

    for message in messages:

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
        "review": final_review,
    }


if __name__ == "__main__":

    # Show our logs in the terminal, as "time  message"
    logging.basicConfig(format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logger.setLevel(logging.INFO)

    result = review(sys.argv[1])
    print(json.dumps(result, indent=2))
