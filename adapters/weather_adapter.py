"""Weather domain adapter. Reuses weather_api.py from the Weather
Dashboard project untouched -- this file's only job is mapping its
output into ComparisonField rows.

No field here gets a "winner" -- there's no objectively "better"
temperature or humidity, so higher_is_better stays None throughout.
This is a legitimate, deliberate use of the schema's "no winner" case,
not a gap.
"""

from schema import ComparisonField
from sources.weather_api import get_weather_for_city, CityNotFoundError, WeatherAPIError

DomainError = (CityNotFoundError, WeatherAPIError)


def lookup(city_name: str) -> dict:
    return get_weather_for_city(city_name)


def to_comparison_fields(data_a: dict | None, data_b: dict | None) -> list[ComparisonField]:
    cur_a = data_a["current"] if data_a else {}
    cur_b = data_b["current"] if data_b else {}

    return [
        ComparisonField("Condition", cur_a.get("label"), cur_b.get("label")),
        ComparisonField("Temperature", cur_a.get("temp_c"), cur_b.get("temp_c"), unit="\u00b0C"),
        ComparisonField("Feels Like", cur_a.get("feels_like_c"), cur_b.get("feels_like_c"), unit="\u00b0C"),
        ComparisonField("Humidity", cur_a.get("humidity"), cur_b.get("humidity"), unit="%"),
        ComparisonField("Wind Speed", cur_a.get("wind_kph"), cur_b.get("wind_kph"), unit="km/h"),
    ]


def display_name(data: dict | None, fallback: str) -> str:
    return data["location"]["display_name"] if data else fallback
