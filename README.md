# Compare Two Things

The Phase 3 capstone: one comparison UI sitting on top of four already-
built projects — Weather Dashboard, Currency Converter, Movie Explorer,
and GitHub Profile Analyzer — reusing their API clients completely
unchanged. This project's only job is composition: converting four
unrelated data shapes into one shared schema so a single renderer can
display all of them.

## A note on domains

The original Phase 3 spec sketched this tool around Weather, Football,
Movies, and News. Football's dashboard is a separate Streamlit app (a
different framework entirely, not composable into a shared FastAPI UI),
and the News Aggregator wasn't built. So this version uses the four
FastAPI + Jinja2 projects that actually exist with working, tested API
clients: **Weather, Currency, Movies, GitHub**. Swapping in another
domain later (News, once built) is exactly the "cheap to add" case this
architecture is meant to prove — see "Adding a new domain" below.

## The core idea: one schema, four sources

```python
# schema.py
@dataclass
class ComparisonField:
    label: str
    value_a: Any
    value_b: Any
    higher_is_better: bool | None = None  # None = no meaningful "winner"
    unit: str | None = None
```

Each domain has exactly one adapter function:

```python
def to_comparison_fields(item_a_raw, item_b_raw) -> list[ComparisonField]:
    ...
```

`main.py` and `templates/index.html` never branch on "is this weather or
movies" — they just iterate a `list[ComparisonField]`. The only
domain-specific code lives inside each adapter's mapping function.

## Project structure

```
compare_two_things/
├── main.py                      # FastAPI routes, domain registry, per-side error handling
├── schema.py                     # ComparisonField -- the shared interface
├── sources/                      # Unchanged copies of each project's API client
│   ├── weather_api.py
│   ├── currency_api.py
│   ├── tmdb_api.py
│   └── github_api.py
├── adapters/                     # The only genuinely new code -- one file per domain
│   ├── weather_adapter.py
│   ├── currency_adapter.py
│   ├── movie_adapter.py
│   └── github_adapter.py
├── requirements.txt
├── templates/
│   └── index.html                 # domain-agnostic comparison table
├── static/
│   └── style.css                   # "VS scoreboard" color scheme
└── tests/
    ├── test_schema.py               # winner logic, formatting
    └── test_adapters.py              # each domain's mapping
```

## What each domain compares

| Domain | "Item" | Fields with a winner | Fields with no winner |
|---|---|---|---|
| **Weather** | A city | *(none)* | Temperature, Feels Like, Humidity, Wind, Condition — no city's weather is objectively "better" |
| **Currency** | A target currency (both converted from the same base) | *(none)* | Converted amount, rate, 30-day trend — bigger isn't "better", just a different scale |
| **Movies** | A movie title (top search match) | Rating, Votes | Release Year, Runtime, Genres |
| **GitHub** | A username | Public Repos, Total Stars, Followers | Joined date |

Weather and Currency having zero "winner" fields is a deliberate,
correct use of the schema's `higher_is_better=None` case — not a gap.
Some comparisons genuinely don't have a "better" side.

## Handling missing/asymmetric data

Two layers of graceful degradation:
1. **Field-level**: if one item is missing a piece of data, that cell
   shows `N/A` (`schema.py`'s `ComparisonField.winner` returns `None`
   whenever either value is missing — no crash, no false winner).
2. **Item-level**: if item A's lookup fails entirely (city not found,
   movie not found, GitHub 404, etc.), item B's side still renders in
   full, with a clear per-side error message next to A instead of taking
   the whole comparison down. This is handled in `main.py`'s
   `_safe_lookup()`.

## Running it

```bash
pip install -r requirements.txt
export TMDB_API_KEY="your-key"       # only needed for the Movies tab
export GITHUB_TOKEN="your-token"      # optional, raises GitHub's rate limit
uvicorn main:app --reload --port 8006
```

Then open http://localhost:8006. Weather, Currency, and GitHub (without
a token) work with zero configuration; Movies needs a TMDb key.

## Running the tests

```bash
pip install pytest
python -m pytest tests/ -v
```

22 tests. `test_schema.py` covers the winner-determination logic in
isolation (the part that has to be right for every domain to be right).
`test_adapters.py` covers each domain's mapping against realistic mocked
source data, including the missing-side case. No real network calls or
API keys needed for any test.

## Adding a new domain (e.g. News, once built)

1. Copy the source project's API client into `sources/`
2. Write one adapter file with `lookup()`, `to_comparison_fields()`, and
   `display_name()`
3. Register it in `main.py`'s `DOMAINS` dict

No changes needed to `schema.py`, `main.py`'s routing, or the template.
That's the actual payoff of building this architecture now instead of
copy-pasting a new comparison page per domain.
