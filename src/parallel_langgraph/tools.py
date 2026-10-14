import json

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver


def get_facts(submission_key: str) -> str:

    # The submission's own properties plus every node linked to it, with that node's properties
    query = """
    MATCH (s:Submission {name: $key})
    OPTIONAL MATCH (s)-[r]-(n)
    WHERE NOT n:Chunk
    RETURN properties(s) AS submission,
           collect({relationship: type(r), label: labels(n)[0], properties: properties(n)}) AS links
    """

    records, _, _ = driver.execute_query(query, key=submission_key, database_=NEO4J_DATABASE)

    if not records or records[0]["submission"] is None:
        return f"Submission {submission_key} was not found."

    return json.dumps(records[0].data(), default=str)


def get_history(submission_key: str) -> str:

    # Other submissions that share the same insured, ceding company or broker
    query = """
    MATCH (s:Submission {name: $key})-[:HAS_INSURED|CEDED_BY|BROKERED_BY]->(shared)
          <-[:HAS_INSURED|CEDED_BY|BROKERED_BY]-(other:Submission)
    WHERE other <> s
    RETURN other.name AS submission,
           collect(DISTINCT labels(shared)[0] + ': ' + shared.name) AS shared,
           [key IN keys(other) WHERE key CONTAINS 'status' OR key CONTAINS 'decline'
                               | key + ': ' + toString(other[key])] AS status
    """

    records, _, _ = driver.execute_query(query, key=submission_key, database_=NEO4J_DATABASE)

    return json.dumps([record.data() for record in records]) if records else "None"
