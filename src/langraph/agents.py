import copy
import json

from src.langraph.state import CaseState
from src.langraph.prompts import TA_VALIDATE_PROMPT, TA_ANSWER_PROMPT, UW_PROMPT
from src.langraph.llm import call_llm
from src.langraph.tools import cytora_value, find_submission, get_facts


# A fixed "user" message for one-off tasks whose details are all in the prompt
TASK = [{"from": "user", "text": "Do the task described above."}]


def ta_agent(state: CaseState):

    # Job A
    # Later turns: the TA already processed the Cytora JSON, so answer the Underwriter's question
    if state.get("updated_cytora"):
        prompt = TA_ANSWER_PROMPT.format(
            cytora=json.dumps(state["updated_cytora"]),
            facts=state["facts"],
        )
        answer = call_llm(prompt, state["messages"])
        return {"messages": [{"from": "ta", "text": answer}]}

    # Job B
    cytora = state["cytora_json"]

    # 1. Find the matching submission in Neo4j
    submission_key = find_submission(cytora)

    if not submission_key:
        text = (
            "NO SUBMISSION FOUND: no existing submission matches this Cytora JSON "
            f"(insured: {cytora_value(cytora, 'Insured Name')}, "
            f"cedant: {cytora_value(cytora, 'Ceding Company Name')}, "
            f"broker: {cytora_value(cytora, 'Broker Company Name')}). "
            "It is a new submission; new submissions are not handled yet."
        )
        return {"submission_key": "", "messages": [{"from": "ta", "text": text}]}

    facts = get_facts(submission_key)

    # 2. Validate every Cytora field against TIRS (Neo4j)
    validation = json.loads(call_llm(
        TA_VALIDATE_PROMPT.format(cytora=json.dumps(cytora), facts=facts),
        TASK,
        json_mode=True,
    ))

    # 3. Update the Cytora JSON: wrong or empty values are replaced by the TIRS value
    updated_cytora = copy.deepcopy(cytora)
    checks = {check["field"]: check for check in validation["fields"]}
    corrections = []

    for entry in updated_cytora.get("Entries", []):
        check = checks.get(entry["FieldName"])
        if not check:
            continue
        entry["ValidationStatus"] = check["status"]
        if check["status"] in ("MISMATCH", "MISSING") and check.get("tirs_value"):
            corrections.append(
                f"{entry['FieldName']}: '{entry['ExtractedValue']}' corrected to '{check['tirs_value']}'"
            )
            entry["ExtractedValue"] = check["tirs_value"]
            entry["TAChange"] = True

    statuses = [check["status"] for check in validation["fields"]]
    text = (
        f"TA DONE: submission {submission_key} found. Cytora validation: "
        f"{statuses.count('MATCH')} match, {statuses.count('MISMATCH')} mismatch, "
        f"{statuses.count('MISSING')} missing, {statuses.count('NOT IN TIRS')} not in TIRS. "
        f"{len(corrections)} field(s) corrected."
    )

    return {
        "submission_key": submission_key,
        "facts": facts,
        "updated_cytora": updated_cytora,
        "corrections": corrections,
        "messages": [{"from": "ta", "text": text}],
    }


def uw_agent(state: CaseState):

    # The UW reviews the TA's work plus the Stitch Analysis Sheet provided with the case
    prompt = UW_PROMPT.format(
        submission_key=state["submission_key"],
        corrections=json.dumps(state.get("corrections", [])),
        cytora=json.dumps(state["updated_cytora"]),
        sheet=state.get("stitch_sheet") or "(not provided)",
        facts=state["facts"],
    )
    reply = json.loads(call_llm(prompt, state["messages"], json_mode=True))

    if reply.get("type") == "QUESTION":
        return {"messages": [{"from": "uw", "text": f"QUESTION: {reply.get('question', '')}"}]}

    # Safe defaults, in case the LLM leaves a key out
    decision = reply.get("decision", "NO QUOTE")
    reasoning = reply.get("reasoning") or ["No reasoning given."]

    text = f"DECISION: {decision} - " + "; ".join(reasoning)

    return {
        "decision": decision,
        "reasoning": reasoning,
        "auth_preview": reply.get("auth_preview") or {},
        "messages": [{"from": "uw", "text": text}],
    }
