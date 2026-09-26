from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.tirsweb.state import UnderwritingState

from src.tirsweb.clearance import build_clearance_query, MockElasticSearchClient, evaluate_clearance
from src.tirsweb.quote import check_appetite, compute_layer_pricing, generate_quote_letter
from src.tirsweb.ui import TIRSWebUIController
from src.tirsweb.extract import run_multimodal_extraction, synthesize_stitch_worksheet
from src.tirsweb.rag import enrich_company_data, MockChromaDBClient

ui_controller = TIRSWebUIController(headless=True)
es_client = MockElasticSearchClient()
chroma_client = MockChromaDBClient()

# --- Node Implementations (Mock for Phase 1) ---

def email_ingestion_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: email_ingestion_node")
    # Generate 1-page summary and categorize intent
    worksheet = state.get("stitch_worksheet", {})
    worksheet["summary"] = "Mock 1-page summary generated from email."
    
    email_raw = state.get("email_raw", {})
    subject = email_raw.get("subject", "").lower()
    
    if "follow up" in subject or "fwd" in subject:
        email_category = "FOLLOW_UP"
        assigned_queue = "Assigned_TA_Queue"
        ta_actions_pending = ["ACTION_ATTACH_UPDATE_DMS"]
    else:
        email_category = "SUBMISSION"
        assigned_queue = "UW_Queue_1"
        ta_actions_pending = ["ACTION_CLEARANCE_RESOLVE", "ACTION_CREATE_SUBMISSION"]

    audit_trail = state.get("audit_trail", [])
    audit_trail.append(f"email_ingestion_node completed. Category: {email_category}")
    
    return {
        "stitch_worksheet": worksheet,
        "email_category": email_category,
        "assigned_queue": assigned_queue,
        "ta_actions_pending": ta_actions_pending,
        "audit_trail": audit_trail
    }

def clearance_es_node(state: UnderwritingState) -> UnderwritingState:
    print("Executing: clearance_es_node")
    cytora_json = state.get("cytora_json", {"insured_name": "Acme Logistics LLC", "tax_id": "12-3456789"})
    email_raw = state.get("email_raw", {"domain": "acmelogistics.com"})
    
    query = build_clearance_query(cytora_json, email_raw)
    es_response = es_client.search(index="clearance", body=query)
    
    current_broker = "Aon" # Mocked from email/cytora
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
    cytora_json = state.get("cytora_json", {"insured_name": "Acme Logistics LLC"})
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
    
    submission_key = state.get("tirs_submission_key", "SUB-UNKNOWN")
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
    lob = stitch_worksheet.get("deal_metrics", {}).get("line_of_business", "Commercial")
    
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
    appetite_rules = {"max_tiv": 100000000.0, "max_loss_ratio": 35.0}
    is_in_appetite = check_appetite(stitch_worksheet, appetite_rules)
    
    if not is_in_appetite:
        return {
            "auto_quote_approved": False,
            "assigned_queue": "Pending Authorization",
            "audit_trail": state.get("audit_trail", []) + ["auto_quote_engine_node: Declined (Out of Appetite). Routed to Pending Authorization"]
        }
    
    limit = deal_metrics.get("requested_limit", 10000000.0)
    attachment = deal_metrics.get("requested_attachment", 0.0)
    
    layer = compute_layer_pricing(limit=limit, attachment=attachment, base_rate=0.0185, hazard_factor=1.0)
    layer["uw_assist_reasoning"] = "Auto-adjusted based on risk factors, TIRSWeb RAG database guidelines, and Stitch Analysis sheet."
    letter = generate_quote_letter(insured_name="Acme Logistics LLC", broker_firm="Aon", layers=[layer])
    
    audit_trail = state.get("audit_trail", [])
    audit_trail.append("auto_quote_engine_node completed successfully")
    
    return {
        "quote_layers": [layer],
        "quote_letter_content": letter,
        "auto_quote_approved": True,
        "assigned_queue": "Pending Authorization",
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
    if state.get("email_category") == "FOLLOW_UP":
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
    if appetite_fit == "STRONG_FIT":
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
