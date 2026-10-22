import json

from langchain_core.tools import tool

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver


@tool
def get_facts(submission_key: str) -> str:
    """Get all data of a submission from Neo4j (insured, cedant, broker, dates, coverages, ...)."""

    # Some submissions keep their number in "name", others only in "submission_id"
    query = """
    MATCH (s:Submission) WHERE s.name = $key OR s.submission_id = $key
    OPTIONAL MATCH (s)-[r]-(n)
    RETURN properties(s) AS submission,
           collect({relationship: type(r), node: properties(n)}) AS linked
    """

    records, _, _ = driver.execute_query(query, key=submission_key, database_=NEO4J_DATABASE)

    if not records:
        return "Submission not found."

    return json.dumps(records[0].data(), default=str)


@tool
def get_history(submission_key: str) -> str:
    """Get other submissions with the same insured, ceding company or broker."""

    # Older submissions use HAS_INSURED, newer ones INSURED
    query = """
    MATCH (s:Submission)-[:HAS_INSURED|INSURED|CEDED_BY|BROKERED_BY]->(shared)
          <-[:HAS_INSURED|INSURED|CEDED_BY|BROKERED_BY]-(other:Submission)
    WHERE s.name = $key OR s.submission_id = $key
    RETURN coalesce(other.name, other.submission_id) AS submission, shared.name AS shared, properties(other) AS details
    """

    records, _, _ = driver.execute_query(query, key=submission_key, database_=NEO4J_DATABASE)

    if not records:
        return "None"

    return json.dumps([record.data() for record in records], default=str)
