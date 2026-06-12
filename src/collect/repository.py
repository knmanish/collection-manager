"""Persistence behind a storage-agnostic interface.

The service layer depends on the ``Repository`` protocol, never on JSON or any
particular file. Swapping in a ``SqliteRepository`` later means writing one new
class and changing nothing above it.

The on-disk document holds two collections::

    {"version": 2, "items": [...], "wishlist": [...]}

Older shapes (a bare list, or v1 without a wishlist) are detected and migrated
on first read.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from .config import data_path
from .errors import ItemNotFound
from .model import Item, WishlistItem

SCHEMA_VERSION = 2


class Repository(Protocol):
    def all(self) -> list[Item]: ...
    def get(self, item_id: str) -> Item: ...
    def add(self, item: Item) -> Item: ...
    def update(self, item: Item) -> Item: ...
    def delete(self, item_id: str) -> None: ...

    def wishlist_all(self) -> list[WishlistItem]: ...
    def wishlist_get(self, item_id: str) -> WishlistItem: ...
    def wishlist_add(self, item: WishlistItem) -> WishlistItem: ...
    def wishlist_update(self, item: WishlistItem) -> WishlistItem: ...
    def wishlist_delete(self, item_id: str) -> None: ...


class JsonRepository:
    """Stores the whole document (items + wishlist) in a single JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or data_path()

    # ---- internals ------------------------------------------------------------

    def _read_doc(self) -> dict:
        if not self._path.exists():
            return {"items": [], "wishlist": []}
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        versioned = isinstance(raw, dict) and "version" in raw

        item_records = _item_records(raw)
        wl_records = raw.get("wishlist", []) if isinstance(raw, dict) else []
        items = [Item.from_dict(r) for r in item_records]
        wishlist = [WishlistItem.from_dict(r) for r in wl_records]

        # Rewrite once if the file is legacy or an older schema, so migrations
        # (ids, cents, the new wishlist key) become durable.
        if not versioned or raw.get("version", 0) < SCHEMA_VERSION:
            self._write_doc(items, wishlist)
        return {"items": items, "wishlist": wishlist}

    def _write_doc(self, items: list[Item], wishlist: list[WishlistItem]) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "items": [i.to_dict() for i in items],
            "wishlist": [w.to_dict() for w in wishlist],
        }
        text = json.dumps(payload, indent=2)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self._path)  # atomic on POSIX and Windows

    # ---- items ----------------------------------------------------------------

    def all(self) -> list[Item]:
        return self._read_doc()["items"]

    def get(self, item_id: str) -> Item:
        for item in self.all():
            if item.id == item_id:
                return item
        raise ItemNotFound(f"No item with id {item_id!r}.")

    def add(self, item: Item) -> Item:
        doc = self._read_doc()
        doc["items"].append(item)
        self._write_doc(doc["items"], doc["wishlist"])
        return item

    def update(self, item: Item) -> Item:
        doc = self._read_doc()
        for idx, existing in enumerate(doc["items"]):
            if existing.id == item.id:
                doc["items"][idx] = item
                self._write_doc(doc["items"], doc["wishlist"])
                return item
        raise ItemNotFound(f"No item with id {item.id!r}.")

    def delete(self, item_id: str) -> None:
        doc = self._read_doc()
        remaining = [i for i in doc["items"] if i.id != item_id]
        if len(remaining) == len(doc["items"]):
            raise ItemNotFound(f"No item with id {item_id!r}.")
        self._write_doc(remaining, doc["wishlist"])

    # ---- wishlist -------------------------------------------------------------

    def wishlist_all(self) -> list[WishlistItem]:
        return self._read_doc()["wishlist"]

    def wishlist_get(self, item_id: str) -> WishlistItem:
        for item in self.wishlist_all():
            if item.id == item_id:
                return item
        raise ItemNotFound(f"No wishlist item with id {item_id!r}.")

    def wishlist_add(self, item: WishlistItem) -> WishlistItem:
        doc = self._read_doc()
        doc["wishlist"].append(item)
        self._write_doc(doc["items"], doc["wishlist"])
        return item

    def wishlist_update(self, item: WishlistItem) -> WishlistItem:
        doc = self._read_doc()
        for idx, existing in enumerate(doc["wishlist"]):
            if existing.id == item.id:
                doc["wishlist"][idx] = item
                self._write_doc(doc["items"], doc["wishlist"])
                return item
        raise ItemNotFound(f"No wishlist item with id {item.id!r}.")

    def wishlist_delete(self, item_id: str) -> None:
        doc = self._read_doc()
        remaining = [i for i in doc["wishlist"] if i.id != item_id]
        if len(remaining) == len(doc["wishlist"]):
            raise ItemNotFound(f"No wishlist item with id {item_id!r}.")
        self._write_doc(doc["items"], remaining)


def _item_records(raw: object) -> list[dict]:
    """Normalize either the versioned shape or the legacy flat list.

    Legacy items have no ``id`` and store ``value`` as a float; we backfill an
    id and convert the value to integer cents so old data keeps working.
    """
    if isinstance(raw, dict):
        records = list(raw.get("items", []))
    else:
        records = list(raw)  # legacy: a bare list of dicts

    migrated: list[dict] = []
    for rec in records:
        rec = dict(rec)
        if "value" in rec and "value_cents" not in rec:
            try:
                rec["value_cents"] = round(float(rec.pop("value")) * 100)
            except (TypeError, ValueError):
                rec["value_cents"] = 0
        rec.setdefault("currency", "USD")
        migrated.append(rec)
    return migrated
