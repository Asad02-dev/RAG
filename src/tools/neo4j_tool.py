from neo4j import GraphDatabase
from agents import function_tool

from configs.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)


driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)

@function_tool
def neo4j_query(cypher: str) -> str:
    """
    Execute a read-only Cypher query against the Neo4j knowledge graph.

    Use this tool when the user's question requires information
    from the Neo4j knowledge graph.

    Args:
        cypher: A valid read-only Cypher query.
    """

    forbidden_keywords = [
        "CREATE",
        "MERGE",
        "DELETE",
        "DETACH DELETE",
        "SET ",
        "REMOVE ",
        "DROP ",
    ]

    normalized_query = cypher.upper()

    for keyword in forbidden_keywords:
        if keyword in normalized_query:
            return (
                "Write operations are not allowed. "
                "Only read-only Cypher queries are permitted."
            )

    try:
        with driver.session() as session:
            result = session.run(cypher)

            records = [
                record.data()
                for record in result
            ]

            return str(records)

    except Exception as exc:
        return f"Neo4j query failed: {exc}"