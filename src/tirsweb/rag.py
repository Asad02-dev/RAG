from typing import Dict, Any
import configs.constants as const


def enrich_company_data(insured_name: str, address: Dict[str, str]) -> Dict[str, Any]:
    """
    Queries free public web APIs for company enrichment (Mocked).
    """
    print(f"Enriching company data for: {insured_name} at {address}")
    return {
        "market_cap_usd": const.MOCK_COMPANY_MARKET_CAP_USD,
        "employee_count": const.MOCK_COMPANY_EMPLOYEE_COUNT,
        "sanctions_cleared": const.MOCK_COMPANY_SANCTIONS_CLEARED,
        "legal_standing": const.MOCK_COMPANY_LEGAL_STANDING
    }

class MockChromaDBClient:
    def query_appetite(self, line_of_business: str) -> Dict[str, Any]:
        """
        Mocks querying ChromaDB for underwriting appetite.
        """
        print(f"Querying ChromaDB for appetite: {line_of_business}")
        return {
            "appetite_fit": const.AppetiteFit.STRONG_FIT,
            "max_tiv": const.MOCK_APPETITE_MAX_TIV,
            "max_loss_ratio": const.MOCK_APPETITE_MAX_LOSS_RATIO,
            "min_rate_on_line": const.MOCK_APPETITE_MIN_RATE_ON_LINE
        }
