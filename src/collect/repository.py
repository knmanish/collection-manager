"""Persistence behind a storage-agnostic interface.

The service layer depends on the ``Repository`` protocol, never on JSON or any
particular file. Swapping in a ``SqliteRepository`` later means writing one new
class and changing nothing above it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from .config import data_path
from .errors import ItemNotFound
from .model import Item

SCHEMA_VERSION = 1


class Repository(Protocol):
    def all(self) -> list[Item]: ...
    def get(self, item_id: str) -> Item: ...
    def add(self, item: Item) -> Item: ...
    def update(self, item: Item) -> Item: ...
    def delete(self, item_id: str) -> None: ...


class JsonRepository:
    """Stores the whole collection in a single JSON file.

    File shape: ``{"version": 1, "items": [...]}``. A legacy flat list
    (``[{...}, ...]``) is detected and migrated on first read.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or data_path()

    # ---- internals ------------------------------------------------------------

    def _read(self) -> list[Item]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        records = _records_from_raw(raw)
        items = [Item.from_dict(r) for r in records]
        # Legacy files (bare list or no "version") get rewritten once so the
        # freshly-assigned ids become stable instead of changing every read.
        if not (isinstance(raw, dict) and "version" in raw):
            self._write(items)
        return items

    def _write(self, items: list[Item]) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "items": [i.to_dict() for i in items],
        }
        text = json.dumps(payload, indent=2)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self._path)  # atomic on POSIX and Windows

    # ---- Repository protocol --------------------------------------------------

    def all(self) -> list[Item]:
        return self._read()

    def get(self, item_id: str) -> Item:
        for item in self._read():
            if item.id == item_id:
                return item
        raise ItemNotFound(f"No item with id {item_id!r}.")

    def add(self, item: Item) -> Item:
        items = self._read()
        items.append(item)
        self._write(items)
        return item

    def update(self, item: Item) -> Item:
        items = self._read()
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item
                self._write(items)
                return item
        raise ItemNotFound(f"No item with id {item.id!r}.")

    def delete(self, item_id: str) -> None:
        items = self._read()
        remaining = [i for i in items if i.id != item_id]
        if len(remaining) == len(items):
            raise ItemNotFound(f"No item with id {item_id!r}.")
        self._write(remaining)


def _records_from_raw(raw: object) -> list[dict]:
    """Normalize either the versioned shape or the legacy flat list.

    Legacy items have no ``id`` and store ``value`` as a float; we backfill an
    id and convert the value to integer cents so old data keeps working.
    """
    if isinstance(raw, dict):
        return list(raw.get("items", []))

    migrated: list[dict] = []
    for rec in raw:  # legacy: a bare list of dicts
        rec = dict(rec)
        if "value" in rec and "value_cents" not in rec:
            try:
                rec["value_cents"] = round(float(rec.pop("value")) * 100)
            except (TypeError, ValueError):
                rec["value_cents"] = 0
        rec.setdefault("currency", "USD")
        migrated.append(rec)
    return migrated
