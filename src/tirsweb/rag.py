from typing import Dict, Any

def enrich_company_data(insured_name: str, address: Dict[str, str]) -> Dict[str, Any]:
    """
    Queries free public web APIs for company enrichment (Mocked).
    """
    print(f"Enriching company data for: {insured_name} at {address}")
    return {
        "market_cap_usd": 420000000.0,
        "employee_count": 1850,
        "sanctions_cleared": True,
        "legal_standing": "ACTIVE"
    }

class MockChromaDBClient:
    def query_appetite(self, line_of_business: str) -> Dict[str, Any]:
        """
        Mocks querying ChromaDB for underwriting appetite.
        """
        print(f"Querying ChromaDB for appetite: {line_of_business}")
        return {
            "appetite_fit": "STRONG_FIT",
            "max_tiv": 100000000.0,
            "max_loss_ratio": 35.0,
            "min_rate_on_line": 0.015
        }
