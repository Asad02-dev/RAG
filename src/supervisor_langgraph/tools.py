import json

from langchain_core.tools import tool

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver


@tool
def get_facts(submission_id: str) -> str:
    """Look up a submission in Neo4j by its number (e.g. "1547612").
    Returns the submission's properties and every node linked to it."""

    # Some submissions keep their number in "name", others only in "submission_id"
    query = """
    MATCH (s:Submission) WHERE s.name = $id OR s.submission_id = $id
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
