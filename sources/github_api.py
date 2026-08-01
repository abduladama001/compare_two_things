"""Thin client around the GitHub REST API v3.

Auth is optional: unauthenticated requests get 60/hour, a personal access
token (fine-grained, no scopes needed for public data) raises that to
5,000/hour. Set GITHUB_TOKEN as an environment variable to use one -- the
app works without it, just with a much tighter budget.

Endpoints used:
  1. /users/{username}                -- profile summary
  2. /users/{username}/repos          -- repo list (paginated by GitHub,
                                          we request per_page=100 and cap
                                          how many repos we look at)
  3. /repos/{owner}/{repo}/languages  -- one call PER repo (a genuine
                                          fan-out) to get byte-counts per
                                          language, which we sum across
                                          all analyzed repos

Because step 3 fans out to one call per repo, we only run it for the
MAX_REPOS_FOR_LANGUAGES most recently pushed repos rather than every repo
a prolific user has -- otherwise a 200-repo profile alone would burn 200
requests just for the language chart. This cap is the actual rate-limit
lesson this project teaches, distinct from a single-call project like the
News Aggregator.
"""

import os
import time

import requests

BASE_URL = "https://api.github.com"
MAX_REPOS_FOR_LANGUAGES = 30

CACHE_TTL_SECONDS = 900  # 15 minutes
_cache: dict[str, tuple[float, dict]] = {}


class UserNotFoundError(Exception):
    pass


class GitHubAPIError(Exception):
    pass


def _headers() -> dict:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def is_authenticated() -> bool:
    return bool(os.environ.get("GITHUB_TOKEN"))


def _cache_get(key: str) -> dict | None:
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_set(key: str, value: dict) -> None:
    _cache[key] = (time.time(), value)


def _get(path: str, params: dict | None = None) -> dict | list:
    try:
        resp = requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=8)
    except requests.RequestException as exc:
        raise GitHubAPIError(f"Couldn't reach GitHub: {exc}") from exc

    if resp.status_code == 404:
        raise UserNotFoundError("That GitHub username doesn't exist.")

    if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
        reset = resp.headers.get("X-RateLimit-Reset")
        raise GitHubAPIError(
            "GitHub's rate limit has been hit for this key/IP."
            + (f" Resets at unix time {reset}." if reset else "")
            + (" Set GITHUB_TOKEN for a higher limit." if not is_authenticated() else "")
        )

    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise GitHubAPIError(f"GitHub returned an error: {exc}") from exc

    return resp.json()


def get_user_profile(username: str) -> dict:
    cache_key = f"user:{username.lower()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    data = _get(f"/users/{username}")
    result = {
        "username": data["login"],
        "name": data.get("name"),
        "avatar_url": data.get("avatar_url"),
        "bio": data.get("bio"),
        "public_repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "following": data.get("following", 0),
        "created_at": (data.get("created_at") or "")[:10],
        "profile_url": data.get("html_url"),
    }
    _cache_set(cache_key, result)
    return result


def get_user_repos(username: str) -> list[dict]:
    cache_key = f"repos:{username.lower()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached["repos"]

    data = _get(
        f"/users/{username}/repos",
        params={"per_page": 100, "sort": "pushed", "direction": "desc", "type": "owner"},
    )

    repos = [
        {
            "name": r["name"],
            "description": r.get("description"),
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "updated_at": (r.get("pushed_at") or "")[:10],
            "url": r.get("html_url"),
            "full_name": r.get("full_name"),
        }
        for r in data
        if not r.get("fork")  # skip forks -- we care about original work
    ]
    _cache_set(cache_key, {"repos": repos})
    return repos


def get_repo_languages(full_name: str) -> dict:
    """Returns {language: bytes} for one repo. full_name is 'owner/repo'."""
    cache_key = f"langs:{full_name.lower()}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    data = _get(f"/repos/{full_name}/languages")
    _cache_set(cache_key, data)
    return data


def get_language_breakdown(repos: list[dict]) -> dict:
    """Fan out to /languages for the most recently pushed repos (capped),
    then sum byte counts across all of them into overall percentages.
    """
    analyzed = repos[:MAX_REPOS_FOR_LANGUAGES]
    totals: dict[str, int] = {}

    for repo in analyzed:
        if not repo.get("full_name"):
            continue
        try:
            langs = get_repo_languages(repo["full_name"])
        except GitHubAPIError:
            continue  # one repo failing shouldn't sink the whole analysis
        for lang, byte_count in langs.items():
            totals[lang] = totals.get(lang, 0) + byte_count

    total_bytes = sum(totals.values()) or 1
    percentages = {
        lang: round((count / total_bytes) * 100, 1)
        for lang, count in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    }
    return {
        "percentages": percentages,
        "repos_analyzed": len(analyzed),
        "repos_total": len(repos),
    }


def analyze_profile(username: str) -> dict:
    """Full pipeline: profile + repos + aggregated language breakdown."""
    profile = get_user_profile(username)
    repos = get_user_repos(username)
    languages = get_language_breakdown(repos)

    total_stars = sum(r["stars"] for r in repos)
    most_recent = repos[0] if repos else None

    return {
        "profile": profile,
        "repos": repos,
        "languages": languages,
        "total_stars": total_stars,
        "most_recent_repo": most_recent,
    }
