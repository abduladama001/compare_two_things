"""Movie domain adapter. Reuses tmdb_api.py from the Movie Explorer
project untouched. Requires TMDB_API_KEY -- same as that project.
"""

from schema import ComparisonField
from sources.tmdb_api import search_movies, get_movie_detail, TMDbConfigError, TMDbAPIError, MovieNotFoundError

DomainError = (TMDbConfigError, TMDbAPIError, MovieNotFoundError)


class MovieSearchEmptyError(Exception):
    pass


DomainError = DomainError + (MovieSearchEmptyError,)


def lookup(title: str) -> dict:
    results = search_movies(title, page=1)
    if not results["results"]:
        raise MovieSearchEmptyError(f'No movie found matching "{title}".')
    top_match_id = results["results"][0]["id"]
    return get_movie_detail(top_match_id)


def to_comparison_fields(data_a: dict | None, data_b: dict | None) -> list[ComparisonField]:
    return [
        ComparisonField(
            "Rating",
            data_a["rating"] if data_a else None,
            data_b["rating"] if data_b else None,
            higher_is_better=True,
            unit="/10",
        ),
        ComparisonField(
            "Release Year",
            data_a["release_year"] if data_a else None,
            data_b["release_year"] if data_b else None,
        ),
        ComparisonField(
            "Runtime",
            data_a["runtime_minutes"] if data_a else None,
            data_b["runtime_minutes"] if data_b else None,
            unit="min",
        ),
        ComparisonField(
            "Votes",
            data_a["vote_count"] if data_a else None,
            data_b["vote_count"] if data_b else None,
            higher_is_better=True,
        ),
        ComparisonField(
            "Genres",
            ", ".join(data_a["genres"]) if data_a and data_a.get("genres") else None,
            ", ".join(data_b["genres"]) if data_b and data_b.get("genres") else None,
        ),
    ]


def display_name(data: dict | None, fallback: str) -> str:
    return data["title"] if data else fallback
