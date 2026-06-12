"""Live currency conversion with an offline-safe cache.

Rates come from frankfurter.app (free, no API key, European Central Bank data).
They're cached locally with a timestamp; if the network is unavailable we fall
back to the last cached rates, and finally to a hardcoded baseline so the app
never hard-fails on conversion.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone

from .config import rates_path
from .model import SUPPORTED_CURRENCIES

_API = "https://api.frankfurter.dev/v1/latest"
_TIMEOUT = 5  # seconds
_MAX_AGE = 12 * 3600  # refresh at most twice a day

# Last-resort baseline (approximate) used only when there's no cache and no net.
_FALLBACK = {
    "base": "USD",
    "rates": {"USD": 1.0, "EUR": 0.92, "INR": 83.0},
    "date": "fallback",
    "fetched_at": 0.0,
    "stale": True,
}

_SYMBOLS = {"USD": "$", "EUR": "€", "INR": "₹"}


def _fetch_from_api() -> dict:
    others = ",".join(c for c in SUPPORTED_CURRENCIES if c != "USD")
    url = f"{_API}?base=USD&symbols={others}"
    req = urllib.request.Request(url, headers={"User-Agent": "collect/0.2"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    rates = {"USD": 1.0}
    rates.update({k: float(v) for k, v in data.get("rates", {}).items()})
    return {
        "base": "USD",
        "rates": rates,
        "date": data.get("date", ""),
        "fetched_at": time.time(),
        "stale": False,
    }


def _read_cache() -> dict | None:
    path = rates_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(data: dict) -> None:
    try:
        rates_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # caching is best-effort


def get_rates(force_refresh: bool = False) -> dict:
    """Return a rates dict: {base, rates, date, fetched_at, stale}.

    Uses the cache when it's fresh; otherwise tries the API and falls back to
    cache, then to the hardcoded baseline. ``stale`` flags non-live data.
    """
    cache = _read_cache()
    fresh = (
        cache is not None
        and not force_refresh
        and (time.time() - cache.get("fetched_at", 0)) < _MAX_AGE
    )
    if fresh:
        return cache

    try:
        data = _fetch_from_api()
        _write_cache(data)
        return data
    except Exception:
        if cache is not None:
            cache["stale"] = True
            return cache
        return dict(_FALLBACK)


def convert(amount_cents: int, from_currency: str, to_currency: str,
            rates: dict | None = None) -> int:
    """Convert an integer-cents amount between currencies, returning cents."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    if from_currency == to_currency:
        return amount_cents
    table = (rates or get_rates())["rates"]
    if from_currency not in table or to_currency not in table:
        return amount_cents  # unknown currency: leave the number untouched
    usd = amount_cents / table[from_currency]   # to USD base
    return round(usd * table[to_currency])


def symbol(currency: str) -> str:
    return _SYMBOLS.get(currency.upper(), currency.upper() + " ")


def format_amount(amount_cents: int, currency: str) -> str:
    """Human-friendly amount, e.g. '$1,234.50' or '₹45,000.00'."""
    value = amount_cents / 100
    return f"{symbol(currency)}{value:,.2f}"


def rates_age_label(rates: dict) -> str:
    """Short freshness label for the UI."""
    if rates.get("date") == "fallback":
        return "offline estimate"
    fetched = rates.get("fetched_at", 0)
    if not fetched:
        return "unknown"
    dt = datetime.fromtimestamp(fetched, tz=timezone.utc)
    suffix = " (cached)" if rates.get("stale") else ""
    return dt.strftime("%Y-%m-%d %H:%M UTC") + suffix
