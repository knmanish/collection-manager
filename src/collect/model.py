"""The domain model: what an *item* is, in exactly one place.

Every other layer (storage, services, CLI, web) derives its notion of an item
from this dataclass instead of restating the field list.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from uuid import uuid4

from .errors import ValidationError

SUPPORTED_CURRENCIES = ("USD", "EUR", "INR")


def _new_id() -> str:
    return uuid4().hex


@dataclass
class Item:
    """A single object in the collection.

    Money is stored as integer minor units (cents/paise) in ``value_cents`` to
    avoid floating-point drift, together with the ``currency`` it was valued in.
    """

    name: str
    category: str
    brand: str = ""
    acquired: str = ""           # ISO date string, "YYYY-MM-DD" or ""
    value_cents: int = 0
    currency: str = "USD"
    notes: str = ""
    image_url: str = ""          # manual override or cached auto-suggestion
    id: str = field(default_factory=_new_id)

    # ---- construction helpers -------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        name: str,
        category: str,
        brand: str = "",
        acquired: str = "",
        value: float | None = None,
        value_cents: int | None = None,
        currency: str = "USD",
        notes: str = "",
        image_url: str = "",
        valid_categories: list[str] | None = None,
    ) -> "Item":
        """Build a validated Item from raw (often user-supplied) input."""
        name = (name or "").strip()
        if not name:
            raise ValidationError("Name is required.")

        category = (category or "").strip()
        if valid_categories is not None and category not in valid_categories:
            allowed = ", ".join(valid_categories) or "(none defined)"
            raise ValidationError(
                f"Category {category!r} is not one of: {allowed}"
            )

        currency = (currency or "USD").strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            allowed = ", ".join(SUPPORTED_CURRENCIES)
            raise ValidationError(f"Currency must be one of: {allowed}")

        acquired = (acquired or "").strip()
        if acquired:
            try:
                date.fromisoformat(acquired)
            except ValueError:
                raise ValidationError(
                    f"Acquired date {acquired!r} must be in YYYY-MM-DD format."
                )

        cents = _resolve_cents(value=value, value_cents=value_cents)

        return cls(
            name=name,
            category=category,
            brand=(brand or "").strip(),
            acquired=acquired,
            value_cents=cents,
            currency=currency,
            notes=(notes or "").strip(),
            image_url=(image_url or "").strip(),
        )

    # ---- serialization --------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def value(self) -> float:
        """Convenience: major-unit value as a float (display only)."""
        return self.value_cents / 100


def _resolve_cents(*, value: float | None, value_cents: int | None) -> int:
    if value_cents is not None:
        return int(value_cents)
    if value is not None:
        try:
            return round(float(value) * 100)
        except (TypeError, ValueError):
            raise ValidationError(f"Value {value!r} is not a number.")
    return 0


PRIORITIES = ("High", "Medium", "Low")


@dataclass
class WishlistItem:
    """A collectible the user wants but doesn't own yet.

    Mirrors :class:`Item` but carries an estimated target price, a buying
    priority, and an optional source link instead of an acquired date.
    """

    name: str
    category: str
    brand: str = ""
    est_value_cents: int = 0
    currency: str = "USD"
    priority: str = "Medium"
    source_url: str = ""
    notes: str = ""
    image_url: str = ""
    id: str = field(default_factory=_new_id)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        category: str,
        brand: str = "",
        est_value: float | None = None,
        est_value_cents: int | None = None,
        currency: str = "USD",
        priority: str = "Medium",
        source_url: str = "",
        notes: str = "",
        image_url: str = "",
        valid_categories: list[str] | None = None,
    ) -> "WishlistItem":
        name = (name or "").strip()
        if not name:
            raise ValidationError("Name is required.")

        category = (category or "").strip()
        if valid_categories is not None and category not in valid_categories:
            allowed = ", ".join(valid_categories) or "(none defined)"
            raise ValidationError(f"Category {category!r} is not one of: {allowed}")

        currency = (currency or "USD").strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Currency must be one of: {', '.join(SUPPORTED_CURRENCIES)}"
            )

        priority = (priority or "Medium").strip().title()
        if priority not in PRIORITIES:
            priority = "Medium"

        return cls(
            name=name,
            category=category,
            brand=(brand or "").strip(),
            est_value_cents=_resolve_cents(value=est_value, value_cents=est_value_cents),
            currency=currency,
            priority=priority,
            source_url=(source_url or "").strip(),
            notes=(notes or "").strip(),
            image_url=(image_url or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WishlistItem":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def est_value(self) -> float:
        return self.est_value_cents / 100
