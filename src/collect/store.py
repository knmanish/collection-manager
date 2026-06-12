import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_PATH = Path.home() / ".collect" / "collection.json"


def _db_path() -> Path:
    path = Path(os.environ.get("COLLECT_DB", _DEFAULT_PATH))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load() -> list[dict[str, Any]]:
    path = _db_path()
    if not path.exists():
        return []
    with path.open() as f:
        return json.load(f)


def save(items: list[dict[str, Any]]) -> None:
    with _db_path().open("w") as f:
        json.dump(items, f, indent=2)
