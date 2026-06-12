from datetime import date
from typing import Any

from . import store

CATEGORIES = {"watch", "pen", "knife"}


def add_item(
    name: str,
    category: str,
    brand: str,
    acquired: str,
    value: float,
    notes: str,
) -> dict[str, Any]:
    """Add an item and return it. Raises ValueError on invalid input."""
    category = category.lower()
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(sorted(CATEGORIES))}")

    # Validate date format (raises ValueError if malformed)
    date.fromisoformat(acquired)

    items = store.load()
    item: dict[str, Any] = {
        "name": name,
        "category": category,
        "brand": brand,
        "acquired": acquired,
        "value": value,
        "notes": notes,
    }
    items.append(item)
    store.save(items)
    return item


def list_items(category: str | None = None) -> list[dict[str, Any]]:
    items = store.load()
    if category:
        items = [i for i in items if i["category"] == category.lower()]
    return items


def remove_item(name: str) -> int:
    """Remove items matching name (case-insensitive). Returns count removed."""
    items = store.load()
    before = len(items)
    items = [i for i in items if i["name"].lower() != name.lower()]
    removed = before - len(items)
    if removed:
        store.save(items)
    return removed


def search_items(query: str) -> list[dict[str, Any]]:
    q = query.lower()
    items = store.load()
    return [
        i for i in items
        if q in i["name"].lower()
        or q in i["brand"].lower()
        or q in i["notes"].lower()
    ]
