"""Filesystem paths and persisted user settings, resolved in one place.

The data directory defaults to ``~/.collect`` and can be overridden with the
``COLLECT_HOME`` environment variable (handy for tests and demos). The legacy
``COLLECT_DB`` variable is still honored so existing data keeps working.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CATEGORIES = ["watch", "pen", "knife"]
DEFAULT_CURRENCY = "USD"


def home_dir() -> Path:
    override = os.environ.get("COLLECT_HOME")
    base = Path(override) if override else Path.home() / ".collect"
    base.mkdir(parents=True, exist_ok=True)
    return base


def data_path() -> Path:
    # Legacy single-file override still supported.
    legacy = os.environ.get("COLLECT_DB")
    if legacy:
        p = Path(legacy)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    return home_dir() / "collection.json"


def config_path() -> Path:
    return home_dir() / "config.json"


def rates_path() -> Path:
    return home_dir() / "rates.json"


@dataclass
class Settings:
    categories: list[str] = field(default_factory=lambda: list(DEFAULT_CATEGORIES))
    display_currency: str = DEFAULT_CURRENCY
    onboarded: bool = False  # has the user dismissed the first-run welcome?

    @classmethod
    def load(cls) -> "Settings":
        path = config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls(
            categories=data.get("categories", list(DEFAULT_CATEGORIES)),
            display_currency=data.get("display_currency", DEFAULT_CURRENCY),
            onboarded=data.get("onboarded", False),
        )

    def save(self) -> None:
        path = config_path()
        payload = {
            "categories": self.categories,
            "display_currency": self.display_currency,
            "onboarded": self.onboarded,
        }
        _atomic_write(path, json.dumps(payload, indent=2))


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + replace so a crash can't truncate the target."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
