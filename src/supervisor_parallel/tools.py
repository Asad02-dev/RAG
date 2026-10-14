import json

from langchain_core.tools import tool

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver


@tool
def get_facts(submission_key: str) -> str:
    """Get all data of a submission from Neo4j (insured, cedant, broker, dates, coverages, ...)."""

    query = """
    MATCH (s:Submission {name: $key})
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

    query = """
    MATCH (s:Submission {name: $key})-[:HAS_INSURED|CEDED_BY|BROKERED_BY]->(shared)
          <-[:HAS_INSURED|CEDED_BY|BROKERED_BY]-(other:Submission)
    RETURN other.name AS submission, shared.name AS shared, properties(other) AS details
    """

    records, _, _ = driver.execute_query(query, key=submission_key, database_=NEO4J_DATABASE)

    if not records:
        return "None"

    return json.dumps([record.data() for record in records], default=str)
