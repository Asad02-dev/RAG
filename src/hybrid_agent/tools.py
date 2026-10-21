import json
import logging

import requests
from langchain_core.tools import tool

from configs.settings import NEO4J_DATABASE
from src.services.neo4j_service import driver

logger = logging.getLogger("hybrid_agent")


@tool
def get_weather(city: str, days: int = 0) -> str:
    """Get the CURRENT weather of a city, and optionally a DAILY FORECAST, live from the Open-Meteo weather API.

    Use this tool when the user asks about the weather, temperature, wind or rain in a place,
    now or in the coming days.
    Inputs:
    - city: only the city name, e.g. "Karachi", "London" or "Whittier" (no state or country).
    - days: 0 = current weather only (default). 1 to 16 = also a daily forecast for that many days,
      starting today (e.g. 7 for "next week" or "next 7 days").
    Returns: JSON with the city, its country, the current temperature (°C), wind speed (km/h),
    precipitation (mm) and weather code; with days > 0 also "forecast": per day the date,
    max and min temperature (°C), total precipitation (mm) and max wind speed (km/h).
    Returns "City ... was not found." if the city is unknown. It does not give past weather.
    """

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


@tool
def get_submission(submission_key: str) -> str:
    """Get all details of ONE insurance submission from the Neo4j database.

    Use this tool when the user asks anything about a submission, or needs a submission's city
    (for example to look up the weather at the submission's location).
    Input: submission_key - the submission number only, e.g. "1547612".
    Returns: JSON with the submission's own fields, plus every linked node: insured, ceding company
    (cedant), broker, contacts, location, line of business, treaty (dates), perils, documents.
    Returns "Submission not found." if the number does not exist.
    """

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
