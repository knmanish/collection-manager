"""Best-effort image suggestions for items, sourced from Wikipedia.

This powers the *auto* half of the hybrid image strategy: when an item has no
manual ``image_url``, we ask Wikipedia for a representative thumbnail based on
its brand and name. A manual URL always wins, and any network failure simply
yields no suggestion (the UI then shows a category placeholder).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

_API = "https://en.wikipedia.org/w/api.php"
_TIMEOUT = 6
# Wikipedia asks for a descriptive User-Agent identifying the app.
_UA = "collect-collection-manager/0.2 (personal collection app)"


def suggest_image(brand: str = "", name: str = "", thumb_size: int = 600) -> str:
    """Return a thumbnail URL for the best-matching Wikipedia page, or "".

    Tries the most specific query first ("brand name"), then falls back to the
    name alone, then the brand alone.
    """
    queries = [
        " ".join(p for p in (brand, name) if p).strip(),
        (name or "").strip(),
        (brand or "").strip(),
    ]
    for q in queries:
        if not q:
            continue
        url = _lookup(q, thumb_size)
        if url:
            return url
    return ""


def _lookup(query: str, thumb_size: int) -> str:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": "1",
        "prop": "pageimages",
        "piprop": "thumbnail",
        "pithumbsize": str(thumb_size),
    }
    url = f"{_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return ""
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        thumb = page.get("thumbnail") or {}
        source = thumb.get("source")
        if source:
            return source
    return ""
