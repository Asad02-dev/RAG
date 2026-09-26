import json
from typing import Dict, Any

def build_clearance_query(cytora_json: Dict[str, Any], email_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the ElasticSearch query payload based on the PRD specification.
    """
    insured_name = cytora_json.get("insured_name", "")
    tax_id = cytora_json.get("tax_id", "")
    normalized_domain = email_raw.get("domain", "")

    query = {
        "query": {
            "bool": {
                "should": [
                    { "fuzzy": { "insured_name": { "value": insured_name, "fuzziness": "AUTO" } } },
                    { "match_phrase": { "tax_id": tax_id } },
                    { "term": { "normalized_domain": normalized_domain } }
                ],
                "minimum_should_match": 1
            }
        }
    }
    return query

class MockElasticSearchClient:
    def search(self, index: str, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mocks the elasticsearch search behavior.
        """
        # Return a mock response that gives a high score
        return {
            "hits": {
                "max_score": 0.96,
                "hits": [
                    {
                        "_id": "SUB-TEST-001",
                        "_score": 0.96,
                        "_source": {
                            "insured_name": body["query"]["bool"]["should"][0]["fuzzy"]["insured_name"]["value"],
                            "broker": "Aon"
                        }
                    }
                ]
            }
        }

def evaluate_clearance(es_response: Dict[str, Any], current_broker: str) -> Dict[str, Any]:
    """
    Evaluates the ES response and computes clearance status, confidence and matches.
    """
    hits = es_response.get("hits", {})
    max_score = hits.get("max_score", 0.0)
    matched_keys = []
    
    if not hits.get("hits"):
        return {
            "clearance_status": "CLEARED",
            "clearance_confidence": 1.0, # Clean new account
            "matched_submission_keys": []
        }
    
    top_hit = hits["hits"][0]
    matched_keys.append(top_hit["_id"])
    prior_broker = top_hit.get("_source", {}).get("broker", "")

    if max_score >= 0.95:
        if prior_broker == current_broker:
            # Renewal or Endorsement Update
            return {
                "clearance_status": "CLEARED_RENEWAL",
                "clearance_confidence": max_score,
                "matched_submission_keys": matched_keys
            }
        else:
            # Broker Conflict
            return {
                "clearance_status": "CONFLICT",
                "clearance_confidence": max_score,
                "matched_submission_keys": matched_keys
            }
    else:
        # Route to TA Review
        return {
            "clearance_status": "TA_REVIEW",
            "clearance_confidence": max_score,
            "matched_submission_keys": matched_keys
        }
