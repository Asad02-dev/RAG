from typing import Dict, Any, List

def check_appetite(stitch_worksheet: Dict[str, Any], appetite_rules: Dict[str, Any]) -> bool:
    """
    Checks if the submission is 100% within the authorized appetite guidelines.
    """
    deal_metrics = stitch_worksheet.get("deal_metrics", {})
    loss_history = stitch_worksheet.get("loss_history_5yr", {})
    
    tiv = deal_metrics.get("total_insurable_value", 0.0)
    loss_ratio = loss_history.get("loss_ratio_pct", 100.0)
    
    max_tiv = appetite_rules.get("max_tiv", 100000000.0)
    max_loss_ratio = appetite_rules.get("max_loss_ratio", 35.0)
    
    if tiv <= max_tiv and loss_ratio < max_loss_ratio:
        return True
    return False

def compute_layer_pricing(limit: float, attachment: float, base_rate: float, hazard_factor: float) -> Dict[str, float]:
    """
    Layer Premium = Limit x Rate on Line (ROL) x Hazard Factor
    """
    rol = base_rate
    premium = limit * rol * hazard_factor
    return {
        "limit": limit,
        "attachment": attachment,
        "premium": premium,
        "rol": rol
    }

def generate_quote_letter(insured_name: str, broker_firm: str, layers: List[Dict[str, float]]) -> str:
    """
    Generates a formal Quote Letter in Markdown.
    """
    letter = f"# FORMAL QUOTE LETTER\n\n"
    letter += f"**Named Insured**: {insured_name}\n"
    letter += f"**Producing Broker**: {broker_firm}\n\n"
    
    letter += "## Quoted Layers\n"
    for idx, layer in enumerate(layers):
        letter += f"- **Layer {idx+1}**: ${layer['limit']:,.2f} part of ${layer['limit'] + layer['attachment']:,.2f} excess of ${layer['attachment']:,.2f}\n"
        letter += f"  - Gross Premium: ${layer['premium']:,.2f}\n"
        
    letter += "\n## Subjectivities\n"
    letter += "- Subject to favorable inspection within 30 days of binding.\n"
    letter += "- Subject to signed and dated SOV.\n"
    
    return letter
