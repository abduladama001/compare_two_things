"""Thin client around The Movie Database (TMDb) API v3.

Requires a free API key (see README for how to get one) passed via the
TMDB_API_KEY environment variable -- never hardcoded here.

Three endpoints used:
  1. /search/movie   -- paginated title search
  2. /movie/popular  -- default landing content, so the page isn't blank
                        before a search (an empty screen should invite
                        action, not just sit there)
  3. /movie/{id}     -- full detail, with `append_to_response=credits` so
                        cast data comes back nested in the same call
                        instead of a second round trip

Responses are cached in-process for CACHE_TTL_SECONDS -- movie metadata
barely changes minute to minute, so this mostly protects against a user
re-searching the same thing or paging back and forth.
"""

import os
import time

import requests

BASE_URL = "https://api.themoviedb.org/3"
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

POSTER_SIZE = "w500"
BACKDROP_SIZE = "w780"

CACHE_TTL_SECONDS = 900  # 15 minutes
_cache: dict[str, tuple[float, dict]] = {}


class TMDbConfigError(Exception):
    """Raised when TMDB_API_KEY isn't set -- a config problem, not a request one."""
    pass


class TMDbAPIError(Exception):
    pass


class MovieNotFoundError(Exception):
    pass


def _get_api_key() -> str:
    api_key = os.environ.get("TMDB_API_KEY")
    if not api_key:
        raise TMDbConfigError(
            "TMDB_API_KEY environment variable is not set. "
            "Get a free key at https://www.themoviedb.org/settings/api and set it before running the app."
        )
    return api_key


def _cache_get(key: str) -> dict | None:
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)


def poster_url(poster_path: str | None, size: str = POSTER_SIZE) -> str | None:
    if not poster_path:
        return None
    return f"{IMAGE_BASE_URL}/{size}{poster_path}"


def _summarize_movie(raw: dict) -> dict:
    """Shrink a raw TMDb movie object down to what the templates need."""
    return {
        "id": raw["id"],
        "title": raw.get("title") or raw.get("original_title"),
        "release_date": raw.get("release_date") or None,
        "release_year": (raw.get("release_date") or "")[:4] or None,
        "rating": round(raw.get("vote_average", 0), 1),
        "vote_count": raw.get("vote_count", 0),
        "overview": raw.get("overview", ""),
        "poster_url": poster_url(raw.get("poster_path")),
    }


def _request(path: str, params: dict) -> dict:
    api_key = _get_api_key()
    full_params = {"api_key": api_key, **params}
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=full_params, timeout=8)
    except requests.RequestException as exc:
        raise TMDbAPIError(f"Couldn't reach TMDb: {exc}") from exc

    if resp.status_code == 404:
        raise MovieNotFoundError("That movie doesn't exist.")
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise TMDbAPIError(f"TMDb returned an error: {exc}") from exc

    return resp.json()


def search_movies(query: str, page: int = 1) -> dict:
    cache_key = f"search:{query.strip().lower()}:{page}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    data = _request("/search/movie", {"query": query, "page": page, "include_adult": "false"})

    result = {
        "query": query,
        "page": data.get("page", 1),
        "total_pages": min(data.get("total_pages", 1), 500),  # TMDb caps at 500 pages anyway
        "total_results": data.get("total_results", 0),
        "results": [_summarize_movie(m) for m in data.get("results", [])],
    }
    _cache_set(cache_key, result)
    return result


def get_popular_movies(page: int = 1) -> dict:
    cache_key = f"popular:{page}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    data = _request("/movie/popular", {"page": page})

    result = {
        "query": None,
        "page": data.get("page", 1),
        "total_pages": min(data.get("total_pages", 1), 500),
        "total_results": data.get("total_results", 0),
        "results": [_summarize_movie(m) for m in data.get("results", [])],
    }
    _cache_set(cache_key, result)
    return result


def get_movie_detail(movie_id: int) -> dict:
    """Full detail for one movie, with cast nested in via append_to_response
    -- one HTTP call instead of two, but still genuinely nested JSON to
    parse: raw["credits"]["cast"] is a list of dicts inside the movie dict.
    """
    cache_key = f"detail:{movie_id}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    data = _request(f"/movie/{movie_id}", {"append_to_response": "credits"})

    genres = [g["name"] for g in data.get("genres", [])]
    cast_raw = data.get("credits", {}).get("cast", [])
    cast = [
        {
            "name": member["name"],
            "character": member.get("character", ""),
            "profile_url": poster_url(member.get("profile_path"), size="w185"),
        }
        for member in cast_raw[:10]  # top-billed only
    ]

    result = {
        "id": data["id"],
        "title": data.get("title"),
        "release_date": data.get("release_date"),
        "release_year": (data.get("release_date") or "")[:4] or None,
        "runtime_minutes": data.get("runtime"),
        "rating": round(data.get("vote_average", 0), 1),
        "vote_count": data.get("vote_count", 0),
        "genres": genres,
        "overview": data.get("overview", ""),
        "tagline": data.get("tagline", ""),
        "poster_url": poster_url(data.get("poster_path")),
        "backdrop_url": poster_url(data.get("backdrop_path"), size=BACKDROP_SIZE),
        "cast": cast,
    }
    _cache_set(cache_key, result)
    return result
