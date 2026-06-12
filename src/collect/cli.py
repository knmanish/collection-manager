"""Command-line adapter: parse args, call the service, print results.

Holds no business logic. Domain errors become a non-zero exit with a message.
"""

from __future__ import annotations

import argparse
import sys

from .errors import CollectError, ItemNotFound
from .model import Item
from .service import CollectionService


def build_parser(categories: list[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collect",
        description="Manage your personal collection.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add an item")
    p_add.add_argument("name")
    p_add.add_argument("--category", "-c", required=True)
    p_add.add_argument("--brand", "-b", default="")
    p_add.add_argument("--acquired", "-a", default="", metavar="YYYY-MM-DD")
    p_add.add_argument("--value", "-v", type=float, default=0.0)
    p_add.add_argument("--currency", default="USD", choices=["USD", "EUR", "INR"])
    p_add.add_argument("--notes", "-n", default="")
    p_add.add_argument("--image-url", default="")

    p_list = sub.add_parser("list", help="List items")
    p_list.add_argument("--category", "-c")

    p_search = sub.add_parser("search", help="Search by name, brand, or notes")
    p_search.add_argument("query")
    p_search.add_argument("--category", "-c")

    p_edit = sub.add_parser("edit", help="Edit an existing item (by id or name)")
    p_edit.add_argument("identifier", help="Item id or exact name")
    p_edit.add_argument("--name")
    p_edit.add_argument("--category", "-c")
    p_edit.add_argument("--brand", "-b")
    p_edit.add_argument("--acquired", "-a", metavar="YYYY-MM-DD")
    p_edit.add_argument("--value", "-v", type=float)
    p_edit.add_argument("--currency", choices=["USD", "EUR", "INR"])
    p_edit.add_argument("--notes", "-n")
    p_edit.add_argument("--image-url")

    p_remove = sub.add_parser("remove", help="Remove an item (by id or name)")
    p_remove.add_argument("identifier", help="Item id or exact name")

    p_cat = sub.add_parser("category", help="Manage categories")
    cat_sub = p_cat.add_subparsers(dest="cat_command", required=True)
    cat_sub.add_parser("list", help="List categories")
    c_add = cat_sub.add_parser("add", help="Add a category")
    c_add.add_argument("name")
    c_rename = cat_sub.add_parser("rename", help="Rename a category")
    c_rename.add_argument("old")
    c_rename.add_argument("new")
    c_remove = cat_sub.add_parser("remove", help="Remove a category")
    c_remove.add_argument("name")
    c_remove.add_argument("--force", action="store_true")

    p_cur = sub.add_parser("currency", help="Get or set the display currency")
    p_cur.add_argument("value", nargs="?", choices=["USD", "EUR", "INR"])

    p_wish = sub.add_parser("wishlist", help="Manage the wishlist")
    wish_sub = p_wish.add_subparsers(dest="wish_command", required=True)
    wish_sub.add_parser("list", help="List wishlist items")
    w_add = wish_sub.add_parser("add", help="Add a wishlist item")
    w_add.add_argument("name")
    w_add.add_argument("--category", "-c", required=True)
    w_add.add_argument("--brand", "-b", default="")
    w_add.add_argument("--est-value", "-v", type=float, default=0.0)
    w_add.add_argument("--currency", default="USD", choices=["USD", "EUR", "INR"])
    w_add.add_argument("--priority", "-p", default="Medium",
                       choices=["High", "Medium", "Low"])
    w_add.add_argument("--source-url", default="")
    w_add.add_argument("--notes", "-n", default="")
    w_remove = wish_sub.add_parser("remove", help="Remove a wishlist item by id or name")
    w_remove.add_argument("identifier")
    w_promote = wish_sub.add_parser("promote", help="Move a wishlist item into the collection")
    w_promote.add_argument("identifier")
    w_promote.add_argument("--acquired", "-a", default="", metavar="YYYY-MM-DD")
    w_promote.add_argument("--value", "-v", type=float)

    return parser


def _resolve(service: CollectionService, identifier: str) -> Item:
    """Accept either an item id or an exact name."""
    try:
        return service.get_item(identifier)
    except ItemNotFound:
        pass
    matches = service.find_by_name(identifier)
    if not matches:
        raise ItemNotFound(f"No item with id or name {identifier!r}.")
    if len(matches) > 1:
        ids = ", ".join(m.id for m in matches)
        raise CollectError(
            f"{len(matches)} items named {identifier!r}; use an id: {ids}"
        )
    return matches[0]


def _print_table(items: list[Item]) -> None:
    if not items:
        print("No items found.")
        return
    rows = [
        {
            "id": i.id[:8],
            "name": i.name,
            "category": i.category,
            "brand": i.brand,
            "acquired": i.acquired,
            "value": f"{i.value:.2f} {i.currency}",
            "notes": i.notes,
        }
        for i in items
    ]
    cols = ["id", "name", "category", "brand", "acquired", "value", "notes"]
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    header = "  ".join(c.upper().ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))


def main() -> None:
    service = CollectionService()
    parser = build_parser(service.list_categories())
    args = parser.parse_args()

    try:
        _dispatch(service, args)
    except CollectError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _dispatch(service: CollectionService, args: argparse.Namespace) -> None:
    if args.command == "add":
        item = service.add_item(
            name=args.name,
            category=args.category,
            brand=args.brand,
            acquired=args.acquired,
            value=args.value,
            currency=args.currency,
            notes=args.notes,
            image_url=args.image_url,
        )
        print(f"Added: {item.name} ({item.category})  id={item.id[:8]}")

    elif args.command == "list":
        _print_table(service.list_items(category=args.category))

    elif args.command == "search":
        results = service.search_items(args.query, category=args.category)
        if not results:
            print(f"No items matching {args.query!r}.")
        else:
            _print_table(results)

    elif args.command == "edit":
        item = _resolve(service, args.identifier)
        updated = service.update_item(
            item.id,
            name=args.name,
            category=args.category,
            brand=args.brand,
            acquired=args.acquired,
            value=args.value,
            currency=args.currency,
            notes=args.notes,
            image_url=args.image_url,
        )
        print(f"Updated: {updated.name}  id={updated.id[:8]}")

    elif args.command == "remove":
        item = _resolve(service, args.identifier)
        service.remove_item(item.id)
        print(f"Removed: {item.name}  id={item.id[:8]}")

    elif args.command == "category":
        _dispatch_category(service, args)

    elif args.command == "currency":
        if args.value:
            service.set_display_currency(args.value)
            print(f"Display currency set to {args.value}.")
        else:
            print(service.get_display_currency())

    elif args.command == "wishlist":
        _dispatch_wishlist(service, args)


def _dispatch_category(service: CollectionService, args: argparse.Namespace) -> None:
    if args.cat_command == "list":
        for c in service.list_categories():
            print(c)
    elif args.cat_command == "add":
        service.add_category(args.name)
        print(f"Added category: {args.name}")
    elif args.cat_command == "rename":
        moved = service.rename_category(args.old, args.new)
        print(f"Renamed {args.old} -> {args.new} ({moved} item(s) updated)")
    elif args.cat_command == "remove":
        service.remove_category(args.name, force=args.force)
        print(f"Removed category: {args.name}")


def _resolve_wishlist(service: CollectionService, identifier: str):
    try:
        return service.get_wishlist_item(identifier)
    except ItemNotFound:
        pass
    matches = [w for w in service.list_wishlist()
               if w.name.lower() == identifier.lower()]
    if not matches:
        raise ItemNotFound(f"No wishlist item with id or name {identifier!r}.")
    if len(matches) > 1:
        ids = ", ".join(m.id for m in matches)
        raise CollectError(f"{len(matches)} wishlist items named {identifier!r}; "
                           f"use an id: {ids}")
    return matches[0]


def _dispatch_wishlist(service: CollectionService, args: argparse.Namespace) -> None:
    if args.wish_command == "list":
        items = service.list_wishlist()
        if not items:
            print("Wishlist is empty.")
            return
        rows = [
            {"id": w.id[:8], "name": w.name, "category": w.category,
             "brand": w.brand, "priority": w.priority,
             "est": f"{w.est_value:.2f} {w.currency}", "notes": w.notes}
            for w in items
        ]
        cols = ["id", "name", "category", "brand", "priority", "est", "notes"]
        widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
        print("  ".join(c.upper().ljust(widths[c]) for c in cols))
        print("-" * (sum(widths.values()) + 2 * (len(cols) - 1)))
        for r in rows:
            print("  ".join(str(r[c]).ljust(widths[c]) for c in cols))
    elif args.wish_command == "add":
        w = service.add_wishlist_item(
            name=args.name, category=args.category, brand=args.brand,
            est_value=args.est_value, currency=args.currency,
            priority=args.priority, source_url=args.source_url, notes=args.notes,
        )
        print(f"Added to wishlist: {w.name} ({w.priority})  id={w.id[:8]}")
    elif args.wish_command == "remove":
        w = _resolve_wishlist(service, args.identifier)
        service.remove_wishlist_item(w.id)
        print(f"Removed from wishlist: {w.name}")
    elif args.wish_command == "promote":
        w = _resolve_wishlist(service, args.identifier)
        item = service.promote_wishlist_item(
            w.id, acquired=args.acquired, value=args.value)
        print(f"Promoted to collection: {item.name}  id={item.id[:8]}")


if __name__ == "__main__":
    main()
