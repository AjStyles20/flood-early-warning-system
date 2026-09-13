"""Small, dependency-free client for short-term rainfall forecast context."""

from __future__ import annotations

from datetime import datetime
import json
from time import monotonic
from urllib.parse import urlencode
from urllib.request import urlopen


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CACHE_SECONDS = 15 * 60
_forecast_cache: dict[tuple[float, float], tuple[float, dict]] = {}


def _weather_label(code: int | None) -> str:
    """Convert the provider's WMO code into a short dashboard label."""
    if code in {51, 53, 55, 56, 57}:
        return "Drizzle"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "Rain"
    if code in {95, 96, 99}:
        return "Thunderstorm"
    if code in {1, 2, 3}:
        return "Cloudy"
    return "Clear"


def get_forecast(latitude: float, longitude: float) -> dict:
    """Return current conditions and six upcoming hourly rainfall observations.

    Results are cached briefly because dashboard refreshes should not repeatedly
    call the weather provider. Network/provider failures intentionally bubble to
    the API layer, which converts them into an unavailable response.
    """
    cache_key = (round(latitude, 3), round(longitude, 3))
    cached = _forecast_cache.get(cache_key)
    if cached and monotonic() - cached[0] < CACHE_SECONDS:
        return cached[1]

    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code,precipitation,rain",
            "hourly": "precipitation_probability,precipitation,rain",
            "forecast_hours": 6,
            "timezone": "Africa/Lagos",
        }
    )
    with urlopen(f"{OPEN_METEO_FORECAST_URL}?{query}", timeout=6) as response:
        payload = json.loads(response.read().decode("utf-8"))

    current = payload.get("current", {})
    hourly = payload.get("hourly", {})
    hours = []
    for index, timestamp in enumerate(hourly.get("time", [])):
        hours.append(
            {
                "time": timestamp,
                "rainfall_mm": hourly.get("rain", [0])[index] or 0,
                "precipitation_mm": hourly.get("precipitation", [0])[index] or 0,
                "precipitation_probability": hourly.get("precipitation_probability", [0])[index] or 0,
            }
        )

    forecast = {
        "available": True,
        "provider": "Open-Meteo",
        "location": {"latitude": latitude, "longitude": longitude},
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "rainfall_mm": current.get("rain") or 0,
            "precipitation_mm": current.get("precipitation") or 0,
            "condition": _weather_label(current.get("weather_code")),
        },
        "next_hours": hours,
    }
    _forecast_cache[cache_key] = (monotonic(), forecast)
    return forecast
