"""Thin client around Open-Meteo's free, no-key APIs.

Two calls per lookup:
  1. Geocoding  -- turn a typed city name into lat/lon
  2. Forecast   -- current conditions + a few days ahead for that lat/lon

Both responses are cached in-process for CACHE_TTL_SECONDS so repeated
searches for the same city (or re-renders of the same page) don't hit the
API more than necessary. Open-Meteo doesn't enforce a hard rate limit the
way football-data.org or NewsAPI do, but caching is still the right habit
to build here -- every Phase 3 project should default to it.
"""

import time
import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CACHE_TTL_SECONDS = 600  # 10 minutes -- weather doesn't change fast enough to justify less
_cache: dict[str, tuple[float, dict]] = {}


class CityNotFoundError(Exception):
    pass


class WeatherAPIError(Exception):
    pass


# WMO weather codes -> (human label, condition family, icon glyph)
# Condition family drives the UI's color theme -- see static/style.css
WMO_CODES = {
    0: ("Clear sky", "clear", "☀️"),
    1: ("Mainly clear", "clear", "🌤️"),
    2: ("Partly cloudy", "clouds", "⛅"),
    3: ("Overcast", "clouds", "☁️"),
    45: ("Fog", "fog", "🌫️"),
    48: ("Depositing rime fog", "fog", "🌫️"),
    51: ("Light drizzle", "rain", "🌦️"),
    53: ("Moderate drizzle", "rain", "🌦️"),
    55: ("Dense drizzle", "rain", "🌧️"),
    56: ("Light freezing drizzle", "snow", "🌨️"),
    57: ("Dense freezing drizzle", "snow", "🌨️"),
    61: ("Slight rain", "rain", "🌦️"),
    63: ("Moderate rain", "rain", "🌧️"),
    65: ("Heavy rain", "rain", "🌧️"),
    66: ("Light freezing rain", "snow", "🌨️"),
    67: ("Heavy freezing rain", "snow", "🌨️"),
    71: ("Slight snow fall", "snow", "🌨️"),
    73: ("Moderate snow fall", "snow", "❄️"),
    75: ("Heavy snow fall", "snow", "❄️"),
    77: ("Snow grains", "snow", "❄️"),
    80: ("Slight rain showers", "rain", "🌦️"),
    81: ("Moderate rain showers", "rain", "🌧️"),
    82: ("Violent rain showers", "storm", "⛈️"),
    85: ("Slight snow showers", "snow", "🌨️"),
    86: ("Heavy snow showers", "snow", "❄️"),
    95: ("Thunderstorm", "storm", "⛈️"),
    96: ("Thunderstorm, slight hail", "storm", "⛈️"),
    99: ("Thunderstorm, heavy hail", "storm", "⛈️"),
}


def _decode_weather_code(code: int) -> dict:
    label, family, icon = WMO_CODES.get(code, ("Unknown", "clear", "❓"))
    return {"code": code, "label": label, "family": family, "icon": icon}


def _cache_get(key: str) -> dict | None:
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)


def geocode_city(city_name: str) -> dict:
    """Turn a typed city name into lat/lon + a display name."""
    cache_key = f"geo:{city_name.strip().lower()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherAPIError(f"Couldn't reach the geocoding service: {exc}") from exc

    data = resp.json()
    results = data.get("results")
    if not results:
        raise CityNotFoundError(f"No location found matching \"{city_name}\".")

    top = results[0]
    display_parts = [top.get("name")]
    if top.get("admin1"):
        display_parts.append(top["admin1"])
    if top.get("country"):
        display_parts.append(top["country"])

    result = {
        "display_name": ", ".join(p for p in display_parts if p),
        "latitude": top["latitude"],
        "longitude": top["longitude"],
        "timezone": top.get("timezone", "auto"),
    }
    _cache_set(cache_key, result)
    return result


def fetch_weather(latitude: float, longitude: float) -> dict:
    """Fetch current conditions + a 5-day forecast for a coordinate pair."""
    cache_key = f"weather:{round(latitude, 2)},{round(longitude, 2)}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "wind_speed_10m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 5,
            },
            timeout=8,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherAPIError(f"Couldn't reach the forecast service: {exc}") from exc

    raw = resp.json()

    current_raw = raw["current"]
    current_condition = _decode_weather_code(current_raw["weather_code"])
    current = {
        "temp_c": round(current_raw["temperature_2m"], 1),
        "feels_like_c": round(current_raw["apparent_temperature"], 1),
        "humidity": current_raw["relative_humidity_2m"],
        "wind_kph": round(current_raw["wind_speed_10m"], 1),
        **current_condition,
    }

    daily_raw = raw["daily"]
    forecast = []
    for i, date in enumerate(daily_raw["time"]):
        condition = _decode_weather_code(daily_raw["weather_code"][i])
        forecast.append({
            "date": date,
            "high_c": round(daily_raw["temperature_2m_max"][i], 1),
            "low_c": round(daily_raw["temperature_2m_min"][i], 1),
            "precip_chance": daily_raw["precipitation_probability_max"][i],
            **condition,
        })

    result = {
        "current": current,
        "forecast": forecast,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
    }
    _cache_set(cache_key, result)
    return result


def get_weather_for_city(city_name: str) -> dict:
    """Full pipeline: city name -> location -> weather. What main.py calls."""
    location = geocode_city(city_name)
    weather = fetch_weather(location["latitude"], location["longitude"])
    return {
        "location": location,
        **weather,
    }
