from typing import Dict, Any, List

def run_multimodal_extraction(raw_attachment_paths: List[str]) -> Dict[str, Any]:
    """
    Mocks the multimodal document extraction for SOVs, loss runs, and slips.
    """
    print(f"Extracting from attachments: {raw_attachment_paths}")
    
    return {
        "sov_data": {
            "total_insurable_value": 75000000.0,
            "location_count": 12,
            "construction_types": ["Fire Resistive", "Masonry Non-Combustible"]
        },
        "loss_run_data": {
            "total_incurred": 142000.0,
            "total_claims_count": 3,
            "loss_ratio_pct": 15.4,
            "large_loss_flag": False
        },
        "slip_data": {
            "requested_limit": 10000000.0,
            "requested_attachment": 0.0,
            "broker_commission": 0.15
        }
    }

def synthesize_stitch_worksheet(cytora_json: Dict[str, Any], multimodal_extractions: Dict[str, Any], company_research: Dict[str, Any], clearance_confidence: float) -> Dict[str, Any]:
    """
    Merges all extracted and enriched data into the Stitch Analysis Worksheet.
    """
    sov_data = multimodal_extractions.get("sov_data", {})
    loss_run_data = multimodal_extractions.get("loss_run_data", {})
    slip_data = multimodal_extractions.get("slip_data", {})
    
    worksheet = {
        "account_overview": {
            "insured_name": cytora_json.get("insured_name", "Acme Logistics LLC"),
            "market_cap_usd": company_research.get("market_cap_usd", 0.0),
            "employee_count": company_research.get("employee_count", 0)
        },
        "deal_metrics": {
            "line_of_business": cytora_json.get("line_of_business", "Commercial Inland Marine"),
            "total_insurable_value": sov_data.get("total_insurable_value", 0.0),
            "requested_limit": slip_data.get("requested_limit", 0.0),
            "requested_attachment": slip_data.get("requested_attachment", 0.0)
        },
        "loss_history_5yr": loss_run_data,
        "underwriting_evaluation": {
            "confidence_index": clearance_confidence,
        }
    }
    
    return worksheet
