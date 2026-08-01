"""Thin client around Frankfurter (frankfurter.app) -- free, no API key,
rates sourced from the European Central Bank.

Three endpoints used:
  1. /currencies         -- supported currency codes + names (rarely changes,
                             so cached much longer than rate data)
  2. /latest             -- today's rate for a from/to pair, with amount applied
  3. /{start}..{end}     -- historical daily rates for a from/to pair, used
                             for the 30-day trend sparkline

All responses are cached in-process. Currency list: 24h TTL, since it
essentially never changes mid-day. Rates: 10 min TTL -- same reasoning as
the weather dashboard, no point re-fetching a live rate every render.
"""

import time
from datetime import date, timedelta

import requests

BASE_URL = "https://api.frankfurter.app"

RATES_CACHE_TTL = 600          # 10 minutes
CURRENCIES_CACHE_TTL = 86400   # 24 hours

_cache: dict[str, tuple[float, dict, float]] = {}
# value tuple = (stored_at, data, ttl) so different endpoints can use different TTLs


class CurrencyAPIError(Exception):
    pass


class UnsupportedCurrencyError(Exception):
    pass


def _cache_get(key: str):
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < hit[2]:
        return hit[1]
    return None


def _cache_set(key: str, value: dict, ttl: float) -> None:
    _cache[key] = (time.time(), value, ttl)


def get_supported_currencies() -> dict:
    """Returns {code: full_name}, e.g. {"USD": "United States Dollar", ...}."""
    cache_key = "currencies"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        resp = requests.get(f"{BASE_URL}/currencies", timeout=8)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise CurrencyAPIError(f"Couldn't reach the currency service: {exc}") from exc

    data = resp.json()
    _cache_set(cache_key, data, CURRENCIES_CACHE_TTL)
    return data


def convert(amount: float, from_currency: str, to_currency: str) -> dict:
    """Convert `amount` from_currency -> to_currency using today's rate."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    cache_key = f"convert:{from_currency}:{to_currency}:{amount}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if from_currency == to_currency:
        result = {
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
            "rate": 1.0,
            "converted": amount,
            "date": date.today().isoformat(),
        }
        _cache_set(cache_key, result, RATES_CACHE_TTL)
        return result

    try:
        resp = requests.get(
            f"{BASE_URL}/latest",
            params={"amount": amount, "from": from_currency, "to": to_currency},
            timeout=8,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise CurrencyAPIError(f"Couldn't reach the currency service: {exc}") from exc

    data = resp.json()
    rates = data.get("rates", {})
    if to_currency not in rates:
        raise UnsupportedCurrencyError(
            f"\"{from_currency}\" to \"{to_currency}\" isn't a supported pair."
        )

    converted_amount = rates[to_currency]
    rate = converted_amount / amount if amount else 0

    result = {
        "from": from_currency,
        "to": to_currency,
        "amount": amount,
        "rate": round(rate, 6),
        "converted": round(converted_amount, 2),
        "date": data.get("date", date.today().isoformat()),
    }
    _cache_set(cache_key, result, RATES_CACHE_TTL)
    return result


def get_history(from_currency: str, to_currency: str, days: int = 30) -> dict:
    """Daily rate history for a pair over the last `days` days."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    cache_key = f"history:{from_currency}:{to_currency}:{days}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if from_currency == to_currency:
        result = {"from": from_currency, "to": to_currency, "points": []}
        _cache_set(cache_key, result, RATES_CACHE_TTL)
        return result

    end = date.today()
    start = end - timedelta(days=days)

    try:
        resp = requests.get(
            f"{BASE_URL}/{start.isoformat()}..{end.isoformat()}",
            params={"from": from_currency, "to": to_currency},
            timeout=8,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise CurrencyAPIError(f"Couldn't reach the currency service: {exc}") from exc

    data = resp.json()
    daily_rates = data.get("rates", {})
    points = [
        {"date": day, "rate": values.get(to_currency)}
        for day, values in sorted(daily_rates.items())
        if to_currency in values
    ]

    result = {"from": from_currency, "to": to_currency, "points": points}
    _cache_set(cache_key, result, RATES_CACHE_TTL)
    return result
