"""Tests for the Neo4j connection (needs a running Neo4j and the NEO4J_* values in .env).

Run as tests:          python -m pytest tests/test_neo4j_connection.py -v
Run the quick check:   python -m tests.test_neo4j_connection
                       (uses the MY_* values at the bottom of this file; empty ones come from .env)
"""

import pytest
from neo4j import GraphDatabase

from configs.settings import (
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
)


@pytest.fixture
def driver():
    if not NEO4J_URI:
        pytest.skip("NEO4J_URI is not set in .env")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    yield driver
    driver.close()


def test_neo4j_settings_are_set():
    assert NEO4J_URI, "NEO4J_URI is not set in .env"
    assert NEO4J_USERNAME, "NEO4J_USERNAME is not set in .env"
    assert NEO4J_PASSWORD, "NEO4J_PASSWORD is not set in .env"


def test_neo4j_connection(driver):
    # Raises an error if the server can't be reached or the login is wrong
    driver.verify_connectivity()


def test_neo4j_simple_query(driver):
    records, _, _ = driver.execute_query("RETURN 1 AS number", database_=NEO4J_DATABASE)

    assert records[0]["number"] == 1


def test_neo4j_has_submissions(driver):
    # The agents need ingested submissions; this only reads, it changes nothing
    records, _, _ = driver.execute_query(
        "MATCH (s:Submission) RETURN count(s) AS total",
        database_=NEO4J_DATABASE,
    )

    assert records[0]["total"] > 0, "No Submission nodes in Neo4j: ingest your data first"


if __name__ == "__main__":

    # ── Put your own values here. Empty ones are taken from .env ──
    # WARNING: do NOT commit a real password; clear it again before you commit.
    MY_URI = ""          # e.g. "bolt://localhost:7687"
    MY_USERNAME = ""     # e.g. "neo4j"
    MY_PASSWORD = ""
    MY_DATABASE = ""     # e.g. "neo4j"

    uri = MY_URI or NEO4J_URI
    username = MY_USERNAME or NEO4J_USERNAME
    password = MY_PASSWORD or NEO4J_PASSWORD
    database = MY_DATABASE or NEO4J_DATABASE

    print(f"Connecting to {uri} as {username} (database: {database or 'default'}) ...")

    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        driver.verify_connectivity()
        print("Connection: OK")

        records, _, _ = driver.execute_query(
            "MATCH (s:Submission) RETURN count(s) AS total",
            database_=database,
        )
        print(f"Submissions in the graph: {records[0]['total']}")

    except Exception as error:
        print(f"Connection FAILED: {error}")

    finally:
        driver.close()
