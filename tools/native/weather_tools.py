import json
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any

logger = logging.getLogger(__name__)

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm"
}

def get_weather(location: str) -> Dict[str, Any]:
    """
    Fetches real-time weather and temperature for any city or location in the world
    using the free, zero-auth Open-Meteo API.
    """
    clean_loc = location.strip()
    if not clean_loc:
        return {"status": "error", "message": "Location parameter cannot be empty"}

    try:
        # 1. Geocode location name to latitude & longitude
        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search?"
            f"name={urllib.parse.quote(clean_loc)}&count=1&language=en&format=json"
        )
        req_geo = urllib.request.Request(geo_url, headers={"User-Agent": "CoreAI-Weather/1.0"})
        with urllib.request.urlopen(req_geo, timeout=6.0) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        results = geo_data.get("results")
        if not results:
            return {
                "status": "error",
                "message": f"Could not find coordinates for location '{clean_loc}'"
            }

        first_match = results[0]
        lat = first_match["latitude"]
        lon = first_match["longitude"]
        place_name = first_match.get("name", clean_loc)
        country = first_match.get("country", "")
        resolved_label = f"{place_name}, {country}" if country else place_name

        # 2. Fetch current weather and temperature
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        )
        req_weather = urllib.request.Request(weather_url, headers={"User-Agent": "CoreAI-Weather/1.0"})
        with urllib.request.urlopen(req_weather, timeout=6.0) as resp:
            weather_data = json.loads(resp.read().decode("utf-8"))

        current = weather_data.get("current", {})
        temp_c = current.get("temperature_2m")
        temp_f = round((temp_c * 9/5) + 32, 1) if temp_c is not None else None
        humidity = current.get("relative_humidity_2m")
        wind_speed = current.get("wind_speed_10m")
        w_code = current.get("weather_code", 0)
        condition = WMO_WEATHER_CODES.get(w_code, "Clear/Sunny")

        return {
            "status": "success",
            "query_location": clean_loc,
            "resolved_location": resolved_label,
            "latitude": lat,
            "longitude": lon,
            "temperature_c": temp_c,
            "temperature_f": temp_f,
            "condition": condition,
            "humidity_pct": humidity,
            "wind_speed_kmh": wind_speed
        }

    except Exception as e:
        logger.error(f"Failed to fetch weather for '{clean_loc}': {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to retrieve weather data for '{clean_loc}': {str(e)}"
        }

weather_schema = {
    "name": "get_weather",
    "description": "Fetches current real-time weather, temperature (Celsius/Fahrenheit), condition, humidity, and wind speed for any city or location in the world.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City or location name (e.g. 'Halle (Saale)', 'Berlin', 'Munich', 'New York', 'Tokyo')"
            }
        },
        "required": ["location"]
    }
}
