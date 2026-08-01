"""Currency domain adapter. Reuses currency_api.py from the Currency
Converter project untouched.

Currency doesn't naturally have "two items to compare" the way a
footballer or a movie does, so this adapter reframes it: the two
"items" are two target currencies, both converted from the same base
amount/currency, compared side by side. No field gets a winner here
either -- a bigger converted number or a bigger exchange rate isn't
objectively "better", it's just a different currency's scale.
"""

from schema import ComparisonField
from sources.currency_api import convert, get_history, CurrencyAPIError, UnsupportedCurrencyError

DomainError = (CurrencyAPIError, UnsupportedCurrencyError)

BASE_AMOUNT = 100.0
BASE_CURRENCY = "USD"


def lookup(target_currency: str) -> dict:
    conversion = convert(BASE_AMOUNT, BASE_CURRENCY, target_currency)
    history = get_history(BASE_CURRENCY, target_currency, days=30)
    trend = _trend_direction(history["points"])
    return {**conversion, "trend": trend}


def _trend_direction(points: list[dict]) -> str:
    rates = [p["rate"] for p in points if p["rate"] is not None]
    if len(rates) < 2:
        return "flat"
    if rates[-1] > rates[0]:
        return "up"
    if rates[-1] < rates[0]:
        return "down"
    return "flat"


def to_comparison_fields(data_a: dict | None, data_b: dict | None) -> list[ComparisonField]:
    return [
        ComparisonField(
            f"{int(BASE_AMOUNT)} {BASE_CURRENCY} converts to",
            data_a["converted"] if data_a else None,
            data_b["converted"] if data_b else None,
            unit=data_a["to"] if data_a else (data_b["to"] if data_b else None),
        ),
        ComparisonField(
            f"Rate (1 {BASE_CURRENCY} =)",
            data_a["rate"] if data_a else None,
            data_b["rate"] if data_b else None,
        ),
        ComparisonField(
            "30-day trend",
            data_a["trend"] if data_a else None,
            data_b["trend"] if data_b else None,
        ),
    ]


def display_name(data: dict | None, fallback: str) -> str:
    return data["to"] if data else fallback
