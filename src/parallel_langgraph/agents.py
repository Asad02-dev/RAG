import json
import time

from src.parallel_langgraph.state import ReviewState
from src.parallel_langgraph.prompts import DATA_CHECK_PROMPT, HISTORY_PROMPT, RISK_PROMPT, MERGE_PROMPT
from src.parallel_langgraph.llm import call_llm
from src.parallel_langgraph.tools import get_facts, get_history


def log(agent: str, text: str):

    # Prints the time, so you can see the three agents start together
    print(f"{time.strftime('%H:%M:%S')}  [{agent}] {text}")


# ── The three agents below run at the same time ──

def data_check_agent(state: ReviewState):

    log("data_check", "started")
    facts = get_facts(state["submission_key"])
    answer = call_llm(DATA_CHECK_PROMPT.format(facts=facts))
    log("data_check", "finished")

    return {"data_check": answer}


def history_agent(state: ReviewState):

    log("history", "started")
    history = get_history(state["submission_key"])
    answer = call_llm(HISTORY_PROMPT.format(submission_key=state["submission_key"], history=history))
    log("history", "finished")

    return {"history": answer}


def risk_agent(state: ReviewState):

    log("risk", "started")
    facts = get_facts(state["submission_key"])
    answer = call_llm(RISK_PROMPT.format(facts=facts))
    log("risk", "finished")

    return {"risk": answer}


# ── Runs only after all three are done ──

def merge_agent(state: ReviewState):

    log("merge", "started (all three agents are done)")
    prompt = MERGE_PROMPT.format(
        submission_key=state["submission_key"],
        data_check=state["data_check"],
        history=state["history"],
        risk=state["risk"],
    )
    review = json.loads(call_llm(prompt, json_mode=True))
    log("merge", "finished")

    return {"review": review}
