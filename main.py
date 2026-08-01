"""FastAPI app for the Compare Two Things Tool.

Run with:  uvicorn main:app --reload --port 8006

This is the Phase 3 capstone: one comparison UI sitting on top of four
already-built projects (Weather Dashboard, Currency Converter, Movie
Explorer, GitHub Profile Analyzer), reusing their API clients unchanged.
Each domain has exactly one adapter function -- to_comparison_fields()
-- that converts its raw data into the shared ComparisonField schema
(schema.py). This file and the template never branch on "which domain
is this" beyond picking the adapter module; the render logic is 100%
domain-agnostic.
"""

from dataclasses import dataclass

from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from adapters import weather_adapter, currency_adapter, movie_adapter, github_adapter

app = FastAPI(title="Compare Two Things")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@dataclass
class Domain:
    key: str
    label: str
    placeholder: str
    example_a: str
    example_b: str
    adapter: object


DOMAINS = {
    "weather": Domain("weather", "Weather", "City name", "Lagos", "London", weather_adapter),
    "currency": Domain("currency", "Currency", "Currency code (e.g. NGN)", "NGN", "EUR", currency_adapter),
    "movies": Domain("movies", "Movies", "Movie title", "Inception", "Interstellar", movie_adapter),
    "github": Domain("github", "GitHub", "GitHub username", "torvalds", "gvanrossum", github_adapter),
}

DEFAULT_DOMAIN = "weather"


@app.get("/")
def compare(
    request: Request,
    domain: str = Query(default=DEFAULT_DOMAIN),
    a: str = Query(default=""),
    b: str = Query(default=""),
):
    if domain not in DOMAINS:
        domain = DEFAULT_DOMAIN
    current = DOMAINS[domain]

    context = {
        "domains": DOMAINS,
        "current_domain": domain,
        "current": current,
        "a": a,
        "b": b,
        "fields": None,
        "name_a": None,
        "name_b": None,
        "error_a": None,
        "error_b": None,
    }

    if a.strip() and b.strip():
        data_a, context["error_a"] = _safe_lookup(current.adapter, a.strip())
        data_b, context["error_b"] = _safe_lookup(current.adapter, b.strip())

        context["fields"] = current.adapter.to_comparison_fields(data_a, data_b)
        context["name_a"] = current.adapter.display_name(data_a, a.strip())
        context["name_b"] = current.adapter.display_name(data_b, b.strip())

    return templates.TemplateResponse(request, "index.html", context)


def _safe_lookup(adapter, query: str):
    """Each side is looked up independently -- if item A fails, item B's
    result still renders, with a clear per-side error instead of taking
    the whole comparison down. This is the "asymmetric data" handling
    the spec calls for, just applied one level up: a missing *item*,
    not just a missing *field*.
    """
    try:
        return adapter.lookup(query), None
    except adapter.DomainError as exc:
        return None, str(exc)
    except Exception as exc:  # noqa: BLE001 -- last-resort guard, still surfaced to the user
        return None, f"Unexpected error: {exc}"
