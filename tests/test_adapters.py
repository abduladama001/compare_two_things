"""Tests for each adapter's to_comparison_fields() -- verifying the
mapping from each domain's raw shape into ComparisonField rows, and that
missing/one-sided data (None for a whole item) is handled without
crashing."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters import weather_adapter, currency_adapter, movie_adapter, github_adapter  # noqa: E402


# ---------- weather ----------

WEATHER_A = {
    "location": {"display_name": "Lagos, Nigeria"},
    "current": {"temp_c": 31.0, "feels_like_c": 35.0, "humidity": 80, "wind_kph": 12.0, "label": "Clear sky"},
}
WEATHER_B = {
    "location": {"display_name": "London, UK"},
    "current": {"temp_c": 18.0, "feels_like_c": 16.0, "humidity": 60, "wind_kph": 20.0, "label": "Overcast"},
}


def test_weather_adapter_maps_both_sides():
    fields = weather_adapter.to_comparison_fields(WEATHER_A, WEATHER_B)
    temp_field = next(f for f in fields if f.label == "Temperature")
    assert temp_field.value_a == 31.0
    assert temp_field.value_b == 18.0
    assert temp_field.winner is None  # weather never has a "winner"


def test_weather_adapter_handles_missing_side():
    fields = weather_adapter.to_comparison_fields(WEATHER_A, None)
    temp_field = next(f for f in fields if f.label == "Temperature")
    assert temp_field.value_a == 31.0
    assert temp_field.value_b is None
    assert temp_field.display_b == "N/A"


def test_weather_display_name():
    assert weather_adapter.display_name(WEATHER_A, "fallback") == "Lagos, Nigeria"
    assert weather_adapter.display_name(None, "Lagos") == "Lagos"


# ---------- currency ----------

CURRENCY_A = {"from": "USD", "to": "NGN", "amount": 100.0, "rate": 1530.42, "converted": 153042.0, "date": "2026-07-21", "trend": "up"}
CURRENCY_B = {"from": "USD", "to": "EUR", "amount": 100.0, "rate": 0.92, "converted": 92.0, "date": "2026-07-21", "trend": "down"}


def test_currency_adapter_maps_both_sides():
    fields = currency_adapter.to_comparison_fields(CURRENCY_A, CURRENCY_B)
    converted_field = fields[0]
    assert converted_field.value_a == 153042.0
    assert converted_field.value_b == 92.0
    assert converted_field.winner is None  # bigger number != "better" currency


def test_currency_adapter_handles_missing_side():
    fields = currency_adapter.to_comparison_fields(None, CURRENCY_B)
    assert fields[0].value_a is None
    assert fields[0].value_b == 92.0


# ---------- movies ----------

MOVIE_A = {
    "title": "Inception", "rating": 8.4, "release_year": "2010", "runtime_minutes": 148,
    "vote_count": 35000, "genres": ["Action", "Sci-Fi"],
}
MOVIE_B = {
    "title": "Interstellar", "rating": 8.6, "release_year": "2014", "runtime_minutes": 169,
    "vote_count": 34000, "genres": ["Adventure", "Drama", "Sci-Fi"],
}


def test_movie_adapter_rating_has_winner():
    fields = movie_adapter.to_comparison_fields(MOVIE_A, MOVIE_B)
    rating_field = next(f for f in fields if f.label == "Rating")
    assert rating_field.winner == "b"  # 8.6 > 8.4


def test_movie_adapter_release_year_has_no_winner():
    fields = movie_adapter.to_comparison_fields(MOVIE_A, MOVIE_B)
    year_field = next(f for f in fields if f.label == "Release Year")
    assert year_field.winner is None


def test_movie_adapter_genres_joined_as_string():
    fields = movie_adapter.to_comparison_fields(MOVIE_A, MOVIE_B)
    genres_field = next(f for f in fields if f.label == "Genres")
    assert genres_field.value_a == "Action, Sci-Fi"


def test_movie_adapter_handles_missing_side():
    fields = movie_adapter.to_comparison_fields(MOVIE_A, None)
    rating_field = next(f for f in fields if f.label == "Rating")
    assert rating_field.winner is None  # can't win against nothing


# ---------- github ----------

GITHUB_A = {
    "profile": {"username": "torvalds", "public_repos": 10, "followers": 200000, "created_at": "2011-09-03"},
    "total_stars": 500,
}
GITHUB_B = {
    "profile": {"username": "gvanrossum", "public_repos": 40, "followers": 30000, "created_at": "2010-01-01"},
    "total_stars": 1200,
}


def test_github_adapter_stars_has_winner():
    fields = github_adapter.to_comparison_fields(GITHUB_A, GITHUB_B)
    stars_field = next(f for f in fields if f.label == "Total Stars")
    assert stars_field.winner == "b"  # 1200 > 500


def test_github_adapter_repos_has_winner():
    fields = github_adapter.to_comparison_fields(GITHUB_A, GITHUB_B)
    repos_field = next(f for f in fields if f.label == "Public Repos")
    assert repos_field.winner == "b"  # 40 > 10


def test_github_adapter_joined_date_has_no_winner():
    fields = github_adapter.to_comparison_fields(GITHUB_A, GITHUB_B)
    joined_field = next(f for f in fields if f.label == "Joined GitHub")
    assert joined_field.winner is None


def test_github_display_name():
    assert github_adapter.display_name(GITHUB_A, "fallback") == "torvalds"
    assert github_adapter.display_name(None, "someone") == "someone"
