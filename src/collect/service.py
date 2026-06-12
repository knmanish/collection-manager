"""Use-case layer: the operations the app supports, independent of how they're
triggered (CLI flags, HTTP forms) or where data lives.

Returns plain domain objects/data and raises domain errors. It never prints and
never imports Flask or argparse.
"""

from __future__ import annotations

from . import images
from .config import Settings
from .errors import CategoryError, ValidationError
from .model import SUPPORTED_CURRENCIES, Item, WishlistItem
from .repository import JsonRepository, Repository


class CollectionService:
    def __init__(
        self,
        repo: Repository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repo = repo or JsonRepository()
        self.settings = settings or Settings.load()

    # ---- items ----------------------------------------------------------------

    def add_item(self, **fields) -> Item:
        item = Item.create(valid_categories=self.settings.categories, **fields)
        return self.repo.add(item)

    def get_item(self, item_id: str) -> Item:
        return self.repo.get(item_id)

    def update_item(self, item_id: str, **changes) -> Item:
        existing = self.repo.get(item_id)
        merged = existing.to_dict()
        # Map a convenience "value" (major units) onto value_cents.
        if "value" in changes and changes["value"] is not None:
            merged["value_cents"] = round(float(changes.pop("value")) * 100)
        else:
            changes.pop("value", None)
        for key, val in changes.items():
            if val is not None and key in merged:
                merged[key] = val
        updated = Item.create(
            name=merged["name"],
            category=merged["category"],
            brand=merged["brand"],
            acquired=merged["acquired"],
            value_cents=merged["value_cents"],
            currency=merged["currency"],
            notes=merged["notes"],
            image_url=merged["image_url"],
            valid_categories=self.settings.categories,
        )
        updated.id = existing.id  # preserve identity
        return self.repo.update(updated)

    def remove_item(self, item_id: str) -> None:
        self.repo.delete(item_id)

    def list_items(self, category: str | None = None) -> list[Item]:
        items = self.repo.all()
        if category:
            items = [i for i in items if i.category == category]
        return items

    def search_items(self, query: str, category: str | None = None) -> list[Item]:
        q = query.lower().strip()
        items = self.list_items(category=category)
        if not q:
            return items
        return [
            i for i in items
            if q in i.name.lower()
            or q in i.brand.lower()
            or q in i.notes.lower()
        ]

    def find_by_name(self, name: str) -> list[Item]:
        """Helper for CLI convenience (lets users act by name, not raw id)."""
        n = name.lower().strip()
        return [i for i in self.repo.all() if i.name.lower() == n]

    # ---- images (best-effort, network) ----------------------------------------

    def suggest_image_for(self, item_id: str, *, overwrite: bool = False) -> Item:
        """Fill an item's image_url from the web if it's empty (or overwrite)."""
        item = self.repo.get(item_id)
        if item.image_url and not overwrite:
            return item
        url = images.suggest_image(item.brand, item.name)
        if url:
            item.image_url = url
            self.repo.update(item)
        return item

    def ensure_images(self) -> int:
        """Auto-suggest images for every item missing one. Returns count filled."""
        filled = 0
        for item in self.repo.all():
            if not item.image_url:
                url = images.suggest_image(item.brand, item.name)
                if url:
                    item.image_url = url
                    self.repo.update(item)
                    filled += 1
        return filled

    # ---- categories -----------------------------------------------------------

    def list_categories(self) -> list[str]:
        return list(self.settings.categories)

    def add_category(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Category name is required.")
        if name in self.settings.categories:
            raise CategoryError(f"Category {name!r} already exists.")
        self.settings.categories.append(name)
        self.settings.save()

    def rename_category(self, old: str, new: str) -> int:
        new = (new or "").strip()
        if old not in self.settings.categories:
            raise CategoryError(f"Unknown category {old!r}.")
        if not new:
            raise ValidationError("New category name is required.")
        if new in self.settings.categories and new != old:
            raise CategoryError(f"Category {new!r} already exists.")
        self.settings.categories = [
            new if c == old else c for c in self.settings.categories
        ]
        self.settings.save()
        # Re-point existing items to the new label.
        moved = 0
        for item in self.repo.all():
            if item.category == old:
                item.category = new
                self.repo.update(item)
                moved += 1
        return moved

    def remove_category(self, name: str, *, force: bool = False) -> None:
        if name not in self.settings.categories:
            raise CategoryError(f"Unknown category {name!r}.")
        in_use = [i for i in self.repo.all() if i.category == name]
        if in_use and not force:
            raise CategoryError(
                f"Category {name!r} is used by {len(in_use)} item(s). "
                "Reassign them or pass force to remove anyway."
            )
        self.settings.categories = [
            c for c in self.settings.categories if c != name
        ]
        self.settings.save()

    # ---- wishlist -------------------------------------------------------------

    def list_wishlist(self, category: str | None = None) -> list[WishlistItem]:
        items = self.repo.wishlist_all()
        if category:
            items = [i for i in items if i.category == category]
        # Sort by priority (High first), then name.
        order = {"High": 0, "Medium": 1, "Low": 2}
        return sorted(items, key=lambda w: (order.get(w.priority, 1), w.name.lower()))

    def get_wishlist_item(self, item_id: str) -> WishlistItem:
        return self.repo.wishlist_get(item_id)

    def add_wishlist_item(self, **fields) -> WishlistItem:
        item = WishlistItem.create(valid_categories=self.settings.categories, **fields)
        return self.repo.wishlist_add(item)

    def update_wishlist_item(self, item_id: str, **changes) -> WishlistItem:
        existing = self.repo.wishlist_get(item_id)
        merged = existing.to_dict()
        if "est_value" in changes and changes["est_value"] is not None:
            merged["est_value_cents"] = round(float(changes.pop("est_value")) * 100)
        else:
            changes.pop("est_value", None)
        for key, val in changes.items():
            if val is not None and key in merged:
                merged[key] = val
        updated = WishlistItem.create(
            name=merged["name"],
            category=merged["category"],
            brand=merged["brand"],
            est_value_cents=merged["est_value_cents"],
            currency=merged["currency"],
            priority=merged["priority"],
            source_url=merged["source_url"],
            notes=merged["notes"],
            image_url=merged["image_url"],
            valid_categories=self.settings.categories,
        )
        updated.id = existing.id
        return self.repo.wishlist_update(updated)

    def remove_wishlist_item(self, item_id: str) -> None:
        self.repo.wishlist_delete(item_id)

    def suggest_wishlist_image(self, item_id: str, *, overwrite: bool = False) -> WishlistItem:
        item = self.repo.wishlist_get(item_id)
        if item.image_url and not overwrite:
            return item
        url = images.suggest_image(item.brand, item.name)
        if url:
            item.image_url = url
            self.repo.wishlist_update(item)
        return item

    def promote_wishlist_item(self, item_id: str, *, acquired: str = "",
                              value: float | None = None) -> Item:
        """Move a wishlist entry into the owned collection, then drop it."""
        w = self.repo.wishlist_get(item_id)
        item = self.add_item(
            name=w.name,
            category=w.category,
            brand=w.brand,
            acquired=acquired,
            value_cents=(w.est_value_cents if value is None else round(value * 100)),
            currency=w.currency,
            notes=w.notes,
            image_url=w.image_url,
        )
        self.repo.wishlist_delete(item_id)
        return item

    # ---- settings -------------------------------------------------------------

    def get_display_currency(self) -> str:
        return self.settings.display_currency

    def set_display_currency(self, currency: str) -> None:
        currency = (currency or "").strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            allowed = ", ".join(SUPPORTED_CURRENCIES)
            raise ValidationError(f"Currency must be one of: {allowed}")
        self.settings.display_currency = currency
        self.settings.save()
