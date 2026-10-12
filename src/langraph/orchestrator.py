import os
import sys
import json
import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.langraph.state import CaseState
from src.langraph.prompts import ORCHESTRATOR_PROMPT
from src.langraph.llm import call_llm
from src.langraph.agents import ta_agent, uw_agent
from src.services.neo4j_service import driver


# Every case's state is saved in this file, so it survives restarts
DATABASE_PATH = "data/langraph_cases.db"

# Each case's result (updated Cytora, decision, auth preview) is written here as JSON
RESULTS_FOLDER = "data/langraph_results"

# Safety limit for the back and forth in one user message
MAX_TURNS = 8


# ── 1. Orchestrator agent: decides who works next ──

def orchestrator(state: CaseState):

    if state["turns"] >= MAX_TURNS:
        return {"next": "end"}

    reply = json.loads(
        call_llm(ORCHESTRATOR_PROMPT, state["messages"], json_mode=True)
    )

    # Only "ta", "uw" or "end" are valid; anything else ends the run safely
    next_step = reply.get("next") if reply.get("next") in ("ta", "uw", "end") else "end"

    message = {
        "from": "orchestrator",
        "text": f"-> {next_step}: {reply.get('instruction', '')}",
    }

    return {
        "next": next_step,
        "messages": [message],
        "turns": state["turns"] + 1,
    }


# ── 2. Graph: who exists, and how control moves between them ──

def build_graph():

    graph = StateGraph(CaseState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("ta", ta_agent)
    graph.add_node("uw", uw_agent)

    # Every turn starts at the orchestrator, which routes to TA, UW or the end
    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges(
        "orchestrator",
        lambda state: state["next"],
        {"ta": "ta", "uw": "uw", "end": END},
    )

    # After each agent, control goes back to the orchestrator
    graph.add_edge("ta", "orchestrator")
    graph.add_edge("uw", "orchestrator")

    # SqliteSaver saves every case's state to DATABASE_PATH, by thread_id
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)

    return graph.compile(checkpointer=SqliteSaver(connection))


app = build_graph()


# ── 3. Entry point: send a Cytora JSON or a message into a case ──

def chat(case_id: str, text: str, cytora_json: dict | None = None, stitch_sheet: str = "") -> list:

    # Same case_id = same thread = the conversation continues
    config = {"configurable": {"thread_id": case_id}}

    old_count = len(app.get_state(config).values.get("messages", []))

    new_input = {"messages": [{"from": "user", "text": text}], "turns": 0}
    if cytora_json:
        new_input["cytora_json"] = cytora_json
    if stitch_sheet:
        new_input["stitch_sheet"] = stitch_sheet

    result = app.invoke(new_input, config)

    # Return only the messages created for this user message
    return result["messages"][old_count:]


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print('Usage: python -m src.langraph.orchestrator <case_id> <cytora.json> [<stitch sheet .json or .txt>]')
        print('   or: python -m src.langraph.orchestrator <case_id> "<follow-up message>"')
        print('Example: python -m src.langraph.orchestrator case-1 data/cytora/test_1547612.json data/stitch/test_1547612_stitch.json')
        print('Then:    python -m src.langraph.orchestrator case-1 "The policy limit is USD 10M"')
        sys.exit(1)

    case_id, user_input = sys.argv[1], sys.argv[2]

    # A .json file is a new Cytora JSON (optionally with a Stitch sheet); anything else is a follow-up message
    if user_input.endswith(".json"):
        with open(user_input, encoding="utf-8") as file:
            cytora_json = json.load(file)

        # The Stitch Analysis Sheet comes from the Stitch system; read as plain text (JSON or .txt)
        stitch_sheet = ""
        if len(sys.argv) > 3:
            with open(sys.argv[3], encoding="utf-8") as file:
                stitch_sheet = file.read()

        messages = chat(case_id, "New Cytora JSON received. Please process it.", cytora_json, stitch_sheet)
    else:
        messages = chat(case_id, user_input)

    for message in messages:
        print(f"[{message['from']}] {message['text']}\n")

    # Save the case result (decision, auth preview, TA corrections, updated Cytora) to a JSON file
    state = app.get_state({"configurable": {"thread_id": case_id}}).values
    result = {
        "submission_key": state.get("submission_key", ""),
        "decision": state.get("decision", ""),
        "reasoning": state.get("reasoning", []),
        "auth_preview": state.get("auth_preview", {}),
        "corrections": state.get("corrections", []),
        "updated_cytora": state.get("updated_cytora", {}),
    }

    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    result_path = f"{RESULTS_FOLDER}/{case_id}.json"
    with open(result_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)

    print(f"Result saved to {result_path}")

    driver.close()
