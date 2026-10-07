from neo4j import GraphDatabase

from configs.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
)


driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(
        NEO4J_USERNAME,
        NEO4J_PASSWORD,
    ),
)


def to_dict(properties):

    # [Property(key="status", value="Quoted")] -> {"status": "Quoted"}
    return {
        prop.key.strip(): prop.value.strip()
        for prop in properties
        if prop.key.strip() and prop.value.strip()
    }


def ingest_triplets(triplets):

    created_count = 0

    for triplet in triplets:

        # Labels and relationship types can't be query parameters; they are safe here
        # because validate_triplets only lets ontology values through.
        query = f"""
        MERGE (
            source:`{triplet.source.label}`
            {{name: $source_name}}
        )
        SET source += $source_properties

        MERGE (
            target:`{triplet.target.label}`
            {{name: $target_name}}
        )
        SET target += $target_properties

        MERGE (
            source
        )-[relationship:`{triplet.relationship}`]->(target)
        SET relationship += $relationship_properties
        """

        driver.execute_query(
            query,
            source_name=triplet.source.name,
            source_properties=to_dict(triplet.source.properties),
            target_name=triplet.target.name,
            target_properties=to_dict(triplet.target.properties),
            relationship_properties=to_dict(triplet.relationship_properties),
            database_=NEO4J_DATABASE,
        )

        created_count += 1

    return created_count


def ingest_standalone_nodes(nodes):

    created_count = 0

    for node in nodes:

        query = f"""
        MERGE (
            node:`{node.label}`
            {{name: $name}}
        )
        SET node += $properties
        """

        driver.execute_query(
            query,
            name=node.name,
            properties=to_dict(node.properties),
            database_=NEO4J_DATABASE,
        )

        created_count += 1

    return created_count
