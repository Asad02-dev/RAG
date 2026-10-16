from neo4j import GraphDatabase
from configs.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
)

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
)

try:
    driver.verify_connectivity()
    print("Neo4j connection successful!")
except Exception as e:
    print("Neo4j connection failed:")
    print(e)
finally:
    driver.close()