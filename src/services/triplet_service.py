import json

from openai import AsyncOpenAI

from configs.settings import OPENAI_API_KEY, NER_OPENAI_MODEL

from src.api.models import TripletExtractionResult

from src.ontology.ontology import (
    ALLOWED_LABELS,
    ALLOWED_RELATIONSHIP_PATTERNS,
    LABEL_DESCRIPTIONS,
)


client = AsyncOpenAI(
    api_key=OPENAI_API_KEY
)


ONTOLOGY_DESCRIPTION = (
    "Node labels:\n"
    + "\n".join(
        f"- {label}: {LABEL_DESCRIPTIONS[label]}" if label in LABEL_DESCRIPTIONS else f"- {label}"
        for label in sorted(ALLOWED_LABELS)
    )
    + "\n\nAllowed relationships (direction matters, use exactly these):\n"
    + "\n".join(
        f"- ({source})-[:{relationship}]->({target})"
        for source, relationship, target in sorted(ALLOWED_RELATIONSHIP_PATTERNS)
    )
)


EXTRACTION_EXAMPLE = """Input JSON:
{
  "submission_id": 1000001,
  "status": "Quoted",
  "premium_amount": "250000.00",
  "currency": "USD",
  "inception_date": "2026-01-01",
  "line_of_business": "Commercial Auto",
  "insured_name": "Blue Harbor Logistics LLC",
  "broker": {"broker_id": 27592, "broker_firm": "Example Brokers Inc", "contact_name": "Jane Doe", "contact_email": "jane.doe@example.com", "commission_pct": "15"},
  "cedant": {"cedant_code": 1683, "cedant_name": "Acme Insurance Co"},
  "risk_location": {"city": "Springfield", "state": "IL", "country": "United States"},
  "ai_enabled": "N",
  "notes": null
}

Correct output:
{
  "triplets": [
    {"source": {"label": "Submission", "name": "1000001", "properties": [
        {"key": "status", "value": "Quoted"},
        {"key": "premium_amount", "value": "250000.00"},
        {"key": "currency", "value": "USD"},
        {"key": "inception_date", "value": "2026-01-01"},
        {"key": "ai_enabled", "value": "N"}]},
     "relationship": "BROKERED_BY",
     "relationship_properties": [{"key": "commission_pct", "value": "15"}],
     "target": {"label": "Broker", "name": "Example Brokers Inc", "properties": [{"key": "broker_id", "value": "27592"}]}},

    {"source": {"label": "Contact", "name": "Jane Doe", "properties": [{"key": "email", "value": "jane.doe@example.com"}]},
     "relationship": "WORKS_AT", "relationship_properties": [],
     "target": {"label": "Broker", "name": "Example Brokers Inc", "properties": []}},

    {"source": {"label": "Submission", "name": "1000001", "properties": []},
     "relationship": "HAS_CONTACT", "relationship_properties": [],
     "target": {"label": "Contact", "name": "Jane Doe", "properties": []}},

    {"source": {"label": "Submission", "name": "1000001", "properties": []},
     "relationship": "HAS_INSURED", "relationship_properties": [],
     "target": {"label": "Insured", "name": "Blue Harbor Logistics LLC", "properties": []}},

    {"source": {"label": "Submission", "name": "1000001", "properties": []},
     "relationship": "CEDED_BY", "relationship_properties": [],
     "target": {"label": "CedingCompany", "name": "Acme Insurance Co", "properties": [{"key": "cedant_code", "value": "1683"}]}},

    {"source": {"label": "Submission", "name": "1000001", "properties": []},
     "relationship": "HAS_LINE_OF_BUSINESS", "relationship_properties": [],
     "target": {"label": "LineOfBusiness", "name": "Commercial Auto", "properties": []}},

    {"source": {"label": "Submission", "name": "1000001", "properties": []},
     "relationship": "LOCATED_IN", "relationship_properties": [],
     "target": {"label": "Location", "name": "Springfield, IL, United States", "properties": [
        {"key": "city", "value": "Springfield"}, {"key": "state", "value": "IL"}, {"key": "country", "value": "United States"}]}}
  ],
  "standalone_nodes": []
}
("notes" is null, so it is skipped. "ai_enabled" is a system flag, so it is a property, not a node.
The broker is the firm; the person is a Contact who works at it. commission_pct describes the broker's role
on this submission, so it sits on the relationship.)"""


EXTRACTION_INSTRUCTIONS = f"""You are a knowledge-graph extraction engine for an insurance and reinsurance company.
You convert JSON business records into triplets (source -> relationship -> target), with properties on nodes and relationships.

# Ontology
{ONTOLOGY_DESCRIPTION}

# Step 1: Decide what is a node
Create a node for a real-world thing that has its own identity and could be shared by other records:
a submission, treaty, company, broker, underwriter, person, contact, location, line of business, peril, coverage, section...
- Use the most specific label that fits (Broker, not Organization, for a broker).
- Use the label descriptions in the ontology to choose the label.
- System flags, internal keys/codes, workflow states and placeholder text ("undefined", "0") are properties, never nodes.
- Free-text descriptions, notes and wording (e.g. a peril or coverage free-text field) are properties of the node they describe, never nodes.
- Never make up a name. If the JSON has no identifying value for something, it is not a node.
- Only use labels from the ontology. If something has no fitting label, do not make it a node; store it as a property of the node it describes.
- Each item in a JSON array that represents a thing is its own node.

# Step 2: Name each node
- `name` is the node's identifying value copied exactly from the JSON.
- NEVER add the label, field name or any other word to the name. Correct: "1547700". Wrong: "Submission 1547700", "ID 1547700".
- If the node has both a readable name and an id/code, `name` is ALWAYS the readable name and the id/code goes in properties.
  Example: {{"CoverageId": "499517", "CoverageName": "Property Damage"}} -> name "Property Damage", property coverage_id "499517".
- If the node only has an id/code, `name` is that id/code.
- Apply these naming rules the same way every time, so the same thing always gets the same name.
- For a location built from separate fields (city, state, country), name it "City, State, Country" (skip missing parts) and also keep each part as a property.

# Step 3: Put facts in properties
Every scalar fact that describes a node (amounts, limits, premiums, rates, percentages, dates, statuses, flags, counts, descriptions, codes) goes in that node's `properties`.
- key: snake_case, based on the JSON field name ("PremiumAmount" -> "premium_amount"). Drop prefixes that only repeat the node (submission_status on a Submission -> status).
- value: copied exactly as in the JSON. Do not convert, round, translate or reformat numbers, dates or currencies.
- Keep related facts separate: an amount and its currency are two properties.
- Attach each fact to the node it describes, not to whichever node is nearest in the JSON.
- Do not repeat the node's name as a property.

# Step 4: Connect nodes as triplets (source -> relationship -> target)
- Each triplet is one allowed relationship, in exactly the direction listed in the ontology. Never reverse one.
- When the same node appears in several triplets, use exactly the same label and name every time.
- Give a node's properties the first time it appears; later triplets may leave its properties empty.
- relationship_properties are facts about the link itself, not about either node
  (e.g. a broker's commission on this submission, a share percentage, a role). Usually this is empty.
- Link each node to the most specific node it belongs to. Example: perils listed under a coverage use (Coverage)-[:COVERS]->(Peril), not the treaty.
- Check both directions: a node can also be the source of an allowed relationship, e.g. (Client)-[:HAS_SUBMISSION]->(Submission).
- If two nodes are related but no allowed relationship fits, do not link them; keep the information as a property instead.
- Only create a relationship when the JSON actually shows that connection. Never invent a link (or an extra node) just to avoid a standalone node.
- If no allowed relationship connects a node to any other node, put it in standalone_nodes.

# Before you answer
- Go through every field, object and array item in the JSON. Each one that fits a label must become a node; do not skip any.

# Rules
- Use only facts present in the JSON. Never invent, infer or complete values.
- Skip null, empty strings, empty lists and placeholders such as "N/A", "null", "-", "none".
- If nothing can be extracted, return empty lists.

# Example (illustration only; never copy these values into your output)
{EXTRACTION_EXAMPLE}
"""


def clean_node(node, data_text):

    # Remove a label prefix the model may still add ("Submission 1547700" -> "1547700"),
    # unless that exact text really is in the JSON.
    # Collapse repeated spaces ("22     - Utilities" -> "22 - Utilities") so the same thing always gets one name
    node.name = " ".join(node.name.split())
    prefix = node.label + " "

    if node.name not in data_text and node.name.lower().startswith(prefix.lower()):
        node.name = node.name[len(prefix):].strip()

    # Drop properties that only repeat the name (e.g. treaty_number "910412328" on Treaty "910412328")
    node.properties = [prop for prop in node.properties if prop.value.strip() != node.name]

    return node


def validate_triplets(result, data_text):

    valid_triplets = []

    for triplet in result.triplets:

        triplet.relationship = triplet.relationship.strip().upper()
        triplet.source = clean_node(triplet.source, data_text)
        triplet.target = clean_node(triplet.target, data_text)

        # Validate complete pattern (this also checks both labels and the relationship)
        pattern = (
            triplet.source.label,
            triplet.relationship,
            triplet.target.label,
        )

        if pattern not in ALLOWED_RELATIONSHIP_PATTERNS:
            continue

        if not triplet.source.name or not triplet.target.name:
            continue

        valid_triplets.append(triplet)

    valid_standalone_nodes = []

    for node in result.standalone_nodes:

        node = clean_node(node, data_text)

        if node.label in ALLOWED_LABELS and node.name:
            valid_standalone_nodes.append(node)

    result.triplets = valid_triplets
    result.standalone_nodes = valid_standalone_nodes

    return result


async def extract_triplets(
    data: dict | list,
) -> TripletExtractionResult:

    data_text = json.dumps(data, ensure_ascii=False, indent=2, default=str)

    response = await client.responses.parse(
        model=NER_OPENAI_MODEL,
        instructions=EXTRACTION_INSTRUCTIONS,
        input=f"Extract the knowledge graph from this JSON:\n\n{data_text}",
        text_format=TripletExtractionResult,
    )

    result = response.output_parsed

    # Final validation
    return validate_triplets(result, data_text)
