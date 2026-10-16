import os
import sys
import json
import time

from langgraph.graph import StateGraph, START, END

from src.parallel_langgraph.state import ReviewState
from src.parallel_langgraph.agents import data_check_agent, history_agent, risk_agent, merge_agent
from src.services.neo4j_service import driver


# Each review is written here as JSON
RESULTS_FOLDER = "data/parallel_results"


# ── 1. Graph: three agents in parallel, then one merge step ──

def build_graph():

    graph = StateGraph(ReviewState)

    graph.add_node("data_check", data_check_agent)
    graph.add_node("history", history_agent)
    graph.add_node("risk", risk_agent)
    graph.add_node("merge", merge_agent)

    # Fan-out: all three start from START, so LangGraph runs them at the same time
    graph.add_edge(START, "data_check")
    graph.add_edge(START, "history")
    graph.add_edge(START, "risk")

    # Fan-in: merge waits until all three are finished
    graph.add_edge(["data_check", "history", "risk"], "merge")

    graph.add_edge("merge", END)

    return graph.compile()


app = build_graph()


# ── 2. Entry point: review one submission ──

def review(submission_key: str) -> dict:

    result = app.invoke({"submission_key": submission_key})
    return result


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage:   python -m src.parallel_langgraph.review <submission_key>")
        print("Example: python -m src.parallel_langgraph.review 1547612")
        sys.exit(1)

    submission_key = sys.argv[1]

    start = time.time()
    result = review(submission_key)
    seconds = time.time() - start

    print("\n" + "=" * 80)
    print(f"[data_check] {result['data_check']}\n")
    print(f"[history]    {result['history']}\n")
    print(f"[risk]       {result['risk']}\n")
    print("=" * 80)
    print(json.dumps(result["review"], indent=2))
    print(f"\nTotal time: {seconds:.1f} seconds")

    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    result_path = f"{RESULTS_FOLDER}/{submission_key}.json"
    with open(result_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    print(f"Result saved to {result_path}")

    driver.close()
