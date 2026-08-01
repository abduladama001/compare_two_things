"""GitHub domain adapter. Reuses github_api.py from the GitHub Profile
Analyzer project untouched.
"""

from schema import ComparisonField
from sources.github_api import analyze_profile, UserNotFoundError, GitHubAPIError

DomainError = (UserNotFoundError, GitHubAPIError)


def lookup(username: str) -> dict:
    return analyze_profile(username)


def to_comparison_fields(data_a: dict | None, data_b: dict | None) -> list[ComparisonField]:
    profile_a = data_a["profile"] if data_a else {}
    profile_b = data_b["profile"] if data_b else {}

    return [
        ComparisonField(
            "Public Repos",
            profile_a.get("public_repos"),
            profile_b.get("public_repos"),
            higher_is_better=True,
        ),
        ComparisonField(
            "Total Stars",
            data_a["total_stars"] if data_a else None,
            data_b["total_stars"] if data_b else None,
            higher_is_better=True,
        ),
        ComparisonField(
            "Followers",
            profile_a.get("followers"),
            profile_b.get("followers"),
            higher_is_better=True,
        ),
        ComparisonField(
            "Joined GitHub",
            profile_a.get("created_at"),
            profile_b.get("created_at"),
        ),
    ]


def display_name(data: dict | None, fallback: str) -> str:
    return data["profile"]["username"] if data else fallback
