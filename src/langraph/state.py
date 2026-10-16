import operator
from typing import Annotated
from typing_extensions import TypedDict


# Shared state of one case (one per thread_id), saved by the checkpointer
class CaseState(TypedDict):

    # Whole conversation: user, orchestrator, ta and uw messages
    messages: Annotated[list, operator.add]

    # Who works next: "ta", "uw" or "end"
    next: str

    # Turns used for the current user message (stops endless back and forth)
    turns: int

    # ── Case data ──

    # Input: the Cytora JSON for this case
    cytora_json: dict

    # TA: the matching submission key in Neo4j ("" = no submission found)
    submission_key: str

    # TA: all facts of that submission from Neo4j (JSON text)
    facts: str

    # TA: the Cytora JSON after validation (fields checked and corrected)
    updated_cytora: dict

    # TA: the list of corrections it made, e.g. "Broker: 'Alliant' corrected to '...'"
    corrections: list

    # Input: the Stitch Analysis Sheet from the Stitch system (JSON or text, kept as text)
    stitch_sheet: str

    # UW: "QUOTE" or "NO QUOTE", with the reasons
    decision: str
    reasoning: list

    # UW: payload for human verification (only when the decision is QUOTE)
    auth_preview: dict
