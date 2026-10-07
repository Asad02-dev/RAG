from neo4j import GraphDatabase
from agents import function_tool

from configs.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)


@function_tool
def get_neo4j_schema() -> str:
    """
    Get the current Neo4j graph schema.

    Returns:
    - Node labels
    - Node properties
    - Relationship types
    - Relationship patterns

    Use this tool before generating a Cypher query
    when the user's question requires Neo4j data.
    """

    node_query = """
    CALL db.schema.nodeTypeProperties()
    YIELD nodeType, nodeLabels, propertyName, propertyTypes
    RETURN nodeType, nodeLabels, propertyName, propertyTypes
    """

    relationship_query = """
    CALL db.schema.relTypeProperties()
    YIELD relType, propertyName, propertyTypes
    RETURN relType, propertyName, propertyTypes
    """

    pattern_query = """
    MATCH (source)-[r]->(target)
    RETURN DISTINCT
        labels(source) AS source_labels,
        type(r) AS relationship,
        labels(target) AS target_labels
    """

    try:
        with driver.session(database=NEO4J_DATABASE) as session:

            node_records = session.run(node_query)
            relationship_records = session.run(relationship_query)
            pattern_records = session.run(pattern_query)

            nodes = [
                record.data()
                for record in node_records
            ]

            relationships = [
                record.data()
                for record in relationship_records
            ]

            patterns = [
                record.data()
                for record in pattern_records
            ]

            return str(
                {
                    "nodes": nodes,
                    "relationships": relationships,
                    "patterns": patterns,
                }
            )

    except Exception as exc:
        return f"Failed to retrieve Neo4j schema: {exc}"