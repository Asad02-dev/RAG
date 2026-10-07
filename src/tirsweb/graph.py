from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import os
from typesafe_sdk import TypeSafeClient, Choice
from src.tirsweb.state import UnderwritingState
import configs.constants as const

from src.tirsweb.clearance import build_clearance_query, MockElasticSearchClient, evaluate_clearance
from src.tirsweb.quote import check_appetite, compute_layer_pricing, generate_quote_letter
from src.tirsweb.ui import TIRSWebUIController
from src.tirsweb.extract import run_multimodal_extraction, synthesize_stitch_worksheet
from src.tirsweb.rag import enrich_company_data, MockChromaDBClient

ui_controller = TIRSWebUIController(headless=True)
es_client = MockElasticSearchClient()
chroma_client = MockChromaDBClient()

# --- Node Implementations (Mock for Phase 1) ---

LLM_CATEGORIES = {
    "Submission": "Request for terms, quote, or renewal terms. Contains submission pack. Not a reply inside an existing thread.",
    "Update": "Supplying info or docs for an existing risk (reply, loss runs, clarification, quote feedback). No new request for terms.",
    "Policy_Review": "Issued policy, binder, endorsement, or dec page attached for review.",
    "Declination": "Deal is explicitly declined, not proceeding, withdrawn, placed elsewhere. Not just the word 'premium decline'.",
    "Other": "Any other intent, noise, or unclassified."
}

def email_ingestion_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: email_ingestion_node")
    
    email_raw = state.get("email_raw", {})
    subject = email_raw.get("subject", "")
    body = email_raw.get("body", "")
    cytora_json = state.get("cytora_json", {})
    cytora_intent = cytora_json.get("intent", "Unknown") # Mock cytora intent
    has_open_submission = state.get("has_open_submission", False) # Mock code signal
    has_bound_submission = state.get("has_bound_submission", False) # Mock code signal
    
    # 1. Code Noise Gate
    if "out of office" in subject.lower():
        # Handle noise early, skip LLM
        return {
            "email_category": "UNCLASSIFIED",
            "assigned_queue": const.TaskQueue.ASSIGNED_TA,
            "ta_actions_pending": [],
            "audit_trail": state.get("audit_trail", []) + ["Noise gate triggered (out of office)"]
        }
        
    # 2. LLM Call
    ts_client = TypeSafeClient(api_key=os.getenv("TYPESAFE_API_KEY", "mock"))
    
    try:
        response = ts_client.system_one(
            state=f"Subject: {subject}\nBody: {body}",
            questions={
                "intent": Choice(
                    instructions="Pick the label that fits the sender's main purpose.",
                    criteria=LLM_CATEGORIES
                )
            }
        )
        llm_label = response.choices["intent"].choice
        llm_confidence = response.choices["intent"].confidence
        evidence = ["(Mocked evidence quote 1)", "(Mocked evidence quote 2)"]
    except Exception as e:
        print(f"Jev API Error: {e}")
        llm_label = "Other"
        llm_confidence = 0.0
        evidence = []

    # 3. Code Reconciliation
    suggested_action = None
    confidence_band = None
    notify_uw = False
    
    # Rule: LLM confidence < 0.70 gives no suggestion
    if llm_confidence < 0.70:
        pass # No suggestion
    
    # 1. Submission/Clearance Input -> suggest 1
    elif llm_label == "Submission":
        # Code checks: No strong match to open submission. Cytora is New/Renewal (or None). Not Follow-up.
        if not has_open_submission and cytora_intent in ["New Business", "Renewal", "Unknown"]:
            suggested_action = 1
            confidence_band = "HIGH" if (cytora_intent in ["New Business", "Renewal"] and llm_confidence >= 0.85) else "MEDIUM"
        
    # 2. Attach/Update DMS -> suggest 9
    elif llm_label == "Update":
        if cytora_intent in ["Follow-up", "Unknown"]:
            suggested_action = 9
            confidence_band = "HIGH" if (has_open_submission or has_bound_submission) and llm_confidence >= 0.85 else "MEDIUM"
            
    # 3. Policy Review -> suggest 10
    elif llm_label == "Policy_Review":
        if has_bound_submission and cytora_intent not in ["New Business", "Renewal"]:
            suggested_action = 10
            confidence_band = "HIGH" if llm_confidence >= 0.85 else "MEDIUM"
            
    # 4. Declination -> suggest 9 + notify UW flag
    elif llm_label == "Declination":
        if has_open_submission and cytora_intent not in ["New Business", "Renewal"]:
            suggested_action = 9
            notify_uw = True
            confidence_band = "HIGH" if llm_confidence >= 0.85 else "MEDIUM"
            
    # Final Routing Mapping Based on Action
    if suggested_action == 1:
        email_category = const.EmailCategory.SUBMISSION
        assigned_queue = const.TaskQueue.UW_QUEUE_1
        ta_actions_pending = [const.TaskAction.CLEARANCE_RESOLVE, const.TaskAction.CREATE_SUBMISSION]
    elif suggested_action == 9:
        email_category = const.EmailCategory.FOLLOW_UP
        assigned_queue = const.TaskQueue.ASSIGNED_TA
        ta_actions_pending = [const.TaskAction.ATTACH_UPDATE_DMS]
    elif suggested_action == 10:
        email_category = const.EmailCategory.FOLLOW_UP # Mapping to existing enum
        assigned_queue = const.TaskQueue.ASSIGNED_TA
        ta_actions_pending = ["ACTION_POLICY_REVIEW"]
    else:
        # No Suggestion / Abstain
        email_category = "UNCLASSIFIED"
        assigned_queue = const.TaskQueue.ASSIGNED_TA
        ta_actions_pending = []

    audit_trail = state.get("audit_trail", [])
    audit_trail.append(f"email_ingestion_node completed. Category: {email_category}")
    audit_trail.append(f"LLM Label: {llm_label}, Conf: {llm_confidence}, Quotes: {evidence}")
    audit_trail.append(f"Reconciled Action: {suggested_action}, Band: {confidence_band}, Notify UW: {notify_uw}")
    
    # Generate 1-page summary and categorize intent
    worksheet = state.get("stitch_worksheet", {})
    worksheet["summary"] = "Mock 1-page summary generated from email."
    
    return {
        "stitch_worksheet": worksheet,
        "email_category": email_category,
        "assigned_queue": assigned_queue,
        "ta_actions_pending": ta_actions_pending,
        "audit_trail": audit_trail
    }

def clearance_es_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: clearance_es_node")
    cytora_json = state.get("cytora_json", {"insured_name": const.MOCK_INSURED_NAME, "tax_id": const.MOCK_TAX_ID})
    email_raw = state.get("email_raw", {"domain": const.MOCK_DOMAIN})
    
    query = build_clearance_query(cytora_json, email_raw)
    es_response = es_client.search(index="clearance", body=query)
    
    current_broker = const.MOCK_BROKER_FIRM # Mocked from email/cytora
    result = evaluate_clearance(es_response, current_broker)
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append(f"clearance_es_node completed with status {result['clearance_status']} (confidence: {result['clearance_confidence']})")
    
    return {
        "clearance_status": result["clearance_status"],
        "clearance_confidence": result["clearance_confidence"],
        "matched_submission_keys": result["matched_submission_keys"],
        "audit_trail": audit_trail
    }

def multimodal_extractor_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: multimodal_extractor_node")
    raw_paths = state.get("raw_attachment_paths", ["sov.xlsx", "loss_runs.pdf"])
    extractions = run_multimodal_extraction(raw_paths)
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("multimodal_extractor_node completed")
    
    return {
        "multimodal_extractions": extractions,
        "audit_trail": audit_trail
    }

def company_enrichment_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: company_enrichment_node")
    cytora_json = state.get("cytora_json", {"insured_name": const.MOCK_INSURED_NAME})
    insured_name = cytora_json.get("insured_name", "Unknown")
    
    research = enrich_company_data(insured_name, {"city": "Chicago"})
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("company_enrichment_node completed")
    
    return {
        "company_research": research,
        "audit_trail": audit_trail
    }

def stitch_synthesis_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: stitch_synthesis_node")
    cytora_json = state.get("cytora_json", {})
    multimodal = state.get("multimodal_extractions", {})
    company_research = state.get("company_research", {})
    clearance_confidence = state.get("clearance_confidence", 0.0)
    
    worksheet = synthesize_stitch_worksheet(cytora_json, multimodal, company_research, clearance_confidence)
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("stitch_synthesis_node completed")
    
    return {
        "stitch_worksheet": worksheet,
        "audit_trail": audit_trail
    }

def tirsweb_ui_executor_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: tirsweb_ui_executor_node")
    completed_actions = state.get("ta_actions_completed", [])
    
    submission_key = state.get("tirs_submission_key", const.MOCK_SUBMISSION_KEY)
    stitch_worksheet = state.get("stitch_worksheet", {})
    clearance_status = state.get("clearance_status", "")
    quote_layers = state.get("quote_layers", [])
    
    ui_actions = ui_controller.run_ui_automation(
        submission_key=submission_key,
        stitch_worksheet=stitch_worksheet,
        clearance_status=clearance_status,
        quote_layers=quote_layers
    )
    completed_actions.extend(ui_actions)
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("tirsweb_ui_executor_node completed")
    
    return {
        "ta_actions_completed": completed_actions,
        "audit_trail": audit_trail
    }

def underwriting_rag_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: underwriting_rag_node")
    stitch_worksheet = state.get("stitch_worksheet", {})
    lob = stitch_worksheet.get("deal_metrics", {}).get("line_of_business", const.MOCK_LOB_COMMERCIAL)
    
    appetite_fit = chroma_client.query_appetite(lob)
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("underwriting_rag_node completed")
    
    return {
        "underwriting_appetite_fit": appetite_fit,
        "audit_trail": audit_trail
    }

def auto_quote_engine_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: auto_quote_engine_node")
    stitch_worksheet = state.get("stitch_worksheet", {})
    deal_metrics = stitch_worksheet.get("deal_metrics", {"total_insurable_value": 75000000.0})
    
    # Mock underwriting guidelines check
    appetite_rules = {"max_tiv": const.MOCK_APPETITE_MAX_TIV, "max_loss_ratio": const.MOCK_APPETITE_MAX_LOSS_RATIO}
    is_in_appetite = check_appetite(stitch_worksheet, appetite_rules)
    
    if not is_in_appetite:
        return {
            "auto_quote_approved": False,
            "assigned_queue": const.TaskQueue.PENDING_AUTHORIZATION,
            "audit_trail": state.get("audit_trail", []) + ["auto_quote_engine_node: Declined (Out of Appetite). Routed to Pending Authorization"]
        }
    
    limit = deal_metrics.get("requested_limit", 10000000.0)
    attachment = deal_metrics.get("requested_attachment", 0.0)
    
    layer = compute_layer_pricing(limit=limit, attachment=attachment, base_rate=0.0185, hazard_factor=1.0)
    layer["uw_assist_reasoning"] = "Auto-adjusted based on risk factors, TIRSWeb RAG database guidelines, and Stitch Analysis sheet."
    letter = generate_quote_letter(insured_name=const.MOCK_INSURED_NAME, broker_firm=const.MOCK_BROKER_FIRM, layers=[layer])
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("auto_quote_engine_node completed successfully")
    
    return {
        "quote_layers": [layer],
        "quote_letter_content": letter,
        "auto_quote_approved": True,
        "assigned_queue": const.TaskQueue.PENDING_AUTHORIZATION,
        "audit_trail": audit_trail
    }

def auto_dms_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: auto_dms_node")
    completed_actions = state.get("ta_actions_completed", [])
    completed_actions.append({"action": "DMS Upload", "status": "SUCCESS"})
    return {
        "ta_actions_completed": completed_actions,
        "audit_trail": ["auto_dms_node completed"]
    }

# --- Routing / Gating Functions ---

def route_after_ingestion(state: UnderwritingState) -> str:
    print("Evaluating: route_after_ingestion")
    if state.get("email_category") == const.EmailCategory.FOLLOW_UP:
        return "auto_dms_node"
    return "clearance_es_node"

def clearance_gate(state: UnderwritingState) -> str:
    print("Evaluating: clearance_gate")
    confidence = state.get("clearance_confidence", 0.0)
    if confidence >= 0.95:
        return "tirsweb_ui_executor_node"
    else:
        # Represents routing to TA Interrupt (for simplicity in graph, we could route to a TA node or interrupt)
        return "ta_review_interrupt"

def quote_gate(state: UnderwritingState) -> str:
    print("Evaluating: quote_gate")
    appetite_fit = state.get("underwriting_appetite_fit", {}).get("appetite_fit", "")
    if appetite_fit == const.AppetiteFit.STRONG_FIT:
        return "auto_quote_engine_node"
    else:
        return "uw_referral_interrupt"

# --- Graph Definition ---

def build_graph():
    workflow = StateGraph(UnderwritingState)

    # Add nodes
    workflow.add_node("email_ingestion_node", email_ingestion_node)
    workflow.add_node("clearance_es_node", clearance_es_node)
    workflow.add_node("multimodal_extractor_node", multimodal_extractor_node)
    workflow.add_node("company_enrichment_node", company_enrichment_node)
    workflow.add_node("stitch_synthesis_node", stitch_synthesis_node)
    workflow.add_node("tirsweb_ui_executor_node", tirsweb_ui_executor_node)
    workflow.add_node("underwriting_rag_node", underwriting_rag_node)
    workflow.add_node("auto_quote_engine_node", auto_quote_engine_node)
    workflow.add_node("auto_dms_node", auto_dms_node)
    
    # We add interrupt nodes to simulate the TA and UW gates
    def ta_review_interrupt(state: UnderwritingState):
        print("INTERRUPT: ta_review_interrupt (TA Assist interaction)")
        audit_trail = state.get("audit_trail", [])
        audit_trail.append("TA Assist: Interaction logged. Auto-adjusting based on TA feedback.")
        return {"audit_trail": audit_trail, "ta_assist_chat_log": [{"role": "ta", "message": "Feedback applied."}]}
        
    def uw_referral_interrupt(state: UnderwritingState):
        print("INTERRUPT: uw_referral_interrupt (UW Assist interaction)")
        audit_trail = state.get("audit_trail", [])
        audit_trail.append("UW Assist: Interaction logged. Terms adjusted based on risk factors.")
        return {"audit_trail": audit_trail, "uw_assist_chat_log": [{"role": "uw", "message": "Terms and Conditions tuned."}]}
        
    workflow.add_node("ta_review_interrupt", ta_review_interrupt)
    workflow.add_node("uw_referral_interrupt", uw_referral_interrupt)

    # Define Edges
    workflow.set_entry_point("email_ingestion_node")
    workflow.add_conditional_edges(
        "email_ingestion_node",
        route_after_ingestion,
        {
            "clearance_es_node": "clearance_es_node",
            "auto_dms_node": "auto_dms_node"
        }
    )
    workflow.add_edge("clearance_es_node", "multimodal_extractor_node")
    workflow.add_edge("multimodal_extractor_node", "company_enrichment_node")
    workflow.add_edge("company_enrichment_node", "stitch_synthesis_node")
    
    # Conditional edge for Clearance
    workflow.add_conditional_edges(
        "stitch_synthesis_node",
        clearance_gate,
        {
            "tirsweb_ui_executor_node": "tirsweb_ui_executor_node",
            "ta_review_interrupt": "ta_review_interrupt"
        }
    )
    
    # After TA Review, we proceed to UI Executor
    workflow.add_edge("ta_review_interrupt", "tirsweb_ui_executor_node")
    
    # From UI Executor to RAG
    workflow.add_edge("tirsweb_ui_executor_node", "underwriting_rag_node")
    
    # Conditional edge for Auto Quote
    workflow.add_conditional_edges(
        "underwriting_rag_node",
        quote_gate,
        {
            "auto_quote_engine_node": "auto_quote_engine_node",
            "uw_referral_interrupt": "uw_referral_interrupt"
        }
    )
    
    # After UW Referral or Auto Quote, proceed to Auto DMS
    workflow.add_edge("uw_referral_interrupt", "auto_dms_node")
    workflow.add_edge("auto_quote_engine_node", "auto_dms_node")
    
    # Finish
    workflow.add_edge("auto_dms_node", END)

    # Compile the graph
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory, interrupt_before=["ta_review_interrupt", "uw_referral_interrupt"])
    
    return app

if __name__ == "__main__":
    app = build_graph()
    print("Graph built successfully.")
    
    # Test 1: New Submission
    initial_state_1 = {
        "tirs_submission_key": "SUB-TEST-001",
        "email_raw": {"subject": "New Submission for Acme"},
        "cytora_json": {},
        "raw_attachment_paths": [],
        "audit_trail": ["Graph Started - Test 1"]
    }
    
    config_1 = {"configurable": {"thread_id": "test_thread_1"}}
    
    print("\n--- Running Graph (Test 1: SUBMISSION) ---")
    for event in app.stream(initial_state_1, config=config_1):
        for node, state_update in event.items():
            print(f"Update from {node}:")
    print("--- Finished Test 1 ---")
    
    # Test 2: Follow-up Email
    initial_state_2 = {
        "tirs_submission_key": "SUB-TEST-001",
        "email_raw": {"subject": "Fwd: Missing SOV attached"},
        "cytora_json": {},
        "raw_attachment_paths": [],
        "audit_trail": ["Graph Started - Test 2"]
    }
    
    config_2 = {"configurable": {"thread_id": "test_thread_2"}}
    
    print("\n--- Running Graph (Test 2: FOLLOW-UP) ---")
    for event in app.stream(initial_state_2, config=config_2):
        for node, state_update in event.items():
            print(f"Update from {node}:")
    print("--- Finished Test 2 ---")
