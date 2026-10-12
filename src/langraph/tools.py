import json

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver


def cytora_value(cytora: dict, field_name: str) -> str:

    # The TIRS description is the official name; fall back to what Cytora extracted
    for entry in cytora.get("Entries", []):
        if entry.get("FieldName") == field_name:
            return (entry.get("TirsDesc") or entry.get("ExtractedValue") or "").strip()

    return ""


def find_submission(cytora: dict) -> str:

    # Match on insured, ceding company and broker: at least 2 of the 3 must match
    query = """
    MATCH (s:Submission)
    OPTIONAL MATCH (s)-[:HAS_INSURED]->(i:Insured)
    OPTIONAL MATCH (s)-[:CEDED_BY]->(c:CedingCompany)
    OPTIONAL MATCH (s)-[:BROKERED_BY]->(b:Broker)
    WITH s,
         CASE WHEN $insured <> '' AND i IS NOT NULL
              AND (toLower(i.name) CONTAINS toLower($insured) OR toLower($insured) CONTAINS toLower(i.name))
              THEN 1 ELSE 0 END
       + CASE WHEN $cedant <> '' AND c IS NOT NULL
              AND (toLower(c.name) CONTAINS toLower($cedant) OR toLower($cedant) CONTAINS toLower(c.name))
              THEN 1 ELSE 0 END
       + CASE WHEN $broker <> '' AND b IS NOT NULL
              AND (toLower(b.name) CONTAINS toLower($broker) OR toLower($broker) CONTAINS toLower(b.name))
              THEN 1 ELSE 0 END AS score
    WHERE score >= 2
    RETURN s.name AS key, score
    ORDER BY score DESC
    LIMIT 1
    """

    records, _, _ = driver.execute_query(
        query,
        insured=cytora_value(cytora, "Insured Name"),
        cedant=cytora_value(cytora, "Ceding Company Name"),
        broker=cytora_value(cytora, "Broker Company Name"),
        database_=NEO4J_DATABASE,
    )

    return records[0]["key"] if records else ""


def get_facts(submission_id: str) -> str:

    # The submission's own properties plus every node linked to it
    query = """
    MATCH (s:Submission {name: $id})
    OPTIONAL MATCH (s)-[r]-(n)
    RETURN properties(s) AS submission,
           collect(type(r) + ' -> ' + labels(n)[0] + ': ' + n.name) AS links
    """

    records, _, _ = driver.execute_query(
        query,
        id=submission_id,
        database_=NEO4J_DATABASE,
    )

    if not records or records[0]["submission"] is None:
        return f"Submission {submission_id} was not found."

    return json.dumps(records[0].data(), default=str)
