from datetime import date
from typing import Any

from . import store

CATEGORIES = {"watch", "pen", "knife"}


def add(
    name: str,
    category: str,
    brand: str,
    acquired: str,
    value: float,
    notes: str,
) -> None:
    category = category.lower()
    if category not in CATEGORIES:
        raise ValueError(f"Category must be one of: {', '.join(sorted(CATEGORIES))}")

    # Validate date format
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
    print(f"Added: {name} ({category})")


def list_items(category: str | None = None) -> None:
    items = store.load()
    if category:
        items = [i for i in items if i["category"] == category.lower()]
    if not items:
        print("No items found.")
        return
    _print_table(items)


def remove(name: str) -> None:
    items = store.load()
    before = len(items)
    items = [i for i in items if i["name"].lower() != name.lower()]
    if len(items) == before:
        print(f"No item named '{name}' found.")
        return
    store.save(items)
    print(f"Removed: {name}")


def search(query: str) -> None:
    q = query.lower()
    items = store.load()
    results = [
        i for i in items
        if q in i["name"].lower()
        or q in i["brand"].lower()
        or q in i["notes"].lower()
    ]
    if not results:
        print(f"No items matching '{query}'.")
        return
    _print_table(results)


def _print_table(items: list[dict[str, Any]]) -> None:
    cols = ["name", "category", "brand", "acquired", "value", "notes"]
    widths = {c: max(len(c), *(len(str(i.get(c, ""))) for i in items)) for c in cols}
    header = "  ".join(c.upper().ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for item in items:
        row = "  ".join(str(item.get(c, "")).ljust(widths[c]) for c in cols)
        print(row)
