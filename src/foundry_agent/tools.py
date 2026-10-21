import json
import logging

import requests
from azure.ai.projects.models import FunctionTool

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver

logger = logging.getLogger("foundry_agent")


# ── The two Python functions. They run here, on our machine, when the Foundry agent asks for them. ──

def get_weather(city: str, days: int = 0) -> str:

    logger.info(f"[get_weather] {city}, days={days}")

    # 1. Find the city's latitude and longitude (Open-Meteo, free, no API key)
    places = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    ).json()

    if not places.get("results"):
        return f"City {city} was not found."

    place = places["results"][0]

    # 2. Get the current weather there, plus a daily forecast if days were asked
    params = {
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "current": "temperature_2m,wind_speed_10m,precipitation,weather_code",
    }
    if days > 0:
        params["daily"] = "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"
        params["forecast_days"] = min(days, 16)   # Open-Meteo gives at most 16 days

    weather = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10).json()

    return json.dumps({
        "city": place["name"],
        "country": place.get("country"),
        "current": weather["current"],
        "forecast": weather.get("daily"),
    })


def get_submission(submission_key: str) -> str:

    logger.info(f"[get_submission] {submission_key}")

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


# Name -> function, so we can run the tool the agent asks for
FUNCTIONS = {"get_weather": get_weather, "get_submission": get_submission}


# ── The same two tools, described for Foundry. The agent reads these descriptions to choose a tool. ──

weather_tool = FunctionTool(
    name="get_weather",
    description=(
        "Get the CURRENT weather of a city, and optionally a DAILY FORECAST, live from the Open-Meteo weather API. "
        "Use it when the user asks about the weather, temperature, wind or rain in a place, now or in the coming days. "
        "Returns JSON with the city, country, current temperature (°C), wind speed (km/h), precipitation (mm), "
        "and with days > 0 also a daily forecast (max/min temperature, total precipitation, max wind). "
        "Returns 'City ... was not found.' if the city is unknown. It does not give past weather."
    ),
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Only the city name, e.g. 'Karachi', 'London' or 'Whittier' (no state or country).",
            },
            "days": {
                "type": "integer",
                "description": "0 = current weather only (default). 1 to 16 = also a daily forecast for that many "
                               "days, starting today (e.g. 7 for 'next week').",
            },
        },
        "required": ["city"],
    },
    strict=False,   # False, because "days" is optional
)

submission_tool = FunctionTool(
    name="get_submission",
    description=(
        "Get all details of ONE insurance submission from the Neo4j database. "
        "Use it when the user asks anything about a submission, or needs a submission's city "
        "(for example to look up the weather at the submission's location). "
        "Returns JSON with the submission's fields plus its insured, ceding company (cedant), broker, contacts, "
        "location, line of business, treaty (dates), perils and documents. "
        "Returns 'Submission not found.' if the number does not exist."
    ),
    parameters={
        "type": "object",
        "properties": {
            "submission_key": {
                "type": "string",
                "description": "The submission number only, e.g. '1547612'.",
            },
        },
        "required": ["submission_key"],
    },
    strict=False,
)
