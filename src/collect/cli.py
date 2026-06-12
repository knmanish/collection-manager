import argparse
import sys
from typing import Any

from . import commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collect",
        description="Manage your personal collection of watches, pens, and knives.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add an item to the collection")
    p_add.add_argument("name", help="Item name")
    p_add.add_argument("--category", "-c", required=True, choices=["watch", "pen", "knife"])
    p_add.add_argument("--brand", "-b", required=True)
    p_add.add_argument("--acquired", "-a", required=True, metavar="YYYY-MM-DD")
    p_add.add_argument("--value", "-v", type=float, default=0.0)
    p_add.add_argument("--notes", "-n", default="")

    # list
    p_list = sub.add_parser("list", help="List items in the collection")
    p_list.add_argument("--category", "-c", choices=["watch", "pen", "knife"])

    # remove
    p_remove = sub.add_parser("remove", help="Remove an item by name")
    p_remove.add_argument("name", help="Exact item name to remove")

    # search
    p_search = sub.add_parser("search", help="Search items by name, brand, or notes")
    p_search.add_argument("query", help="Search query")

    return parser


def _print_table(items: list[dict[str, Any]]) -> None:
    if not items:
        print("No items found.")
        return
    cols = ["name", "category", "brand", "acquired", "value", "notes"]
    widths = {c: max(len(c), *(len(str(i.get(c, ""))) for i in items)) for c in cols}
    header = "  ".join(c.upper().ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for item in items:
        row = "  ".join(str(item.get(c, "")).ljust(widths[c]) for c in cols)
        print(row)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "add":
            item = commands.add_item(
                name=args.name,
                category=args.category,
                brand=args.brand,
                acquired=args.acquired,
                value=args.value,
                notes=args.notes,
            )
            print(f"Added: {item['name']} ({item['category']})")
        elif args.command == "list":
            _print_table(commands.list_items(category=getattr(args, "category", None)))
        elif args.command == "remove":
            removed = commands.remove_item(args.name)
            if removed:
                print(f"Removed: {args.name}")
            else:
                print(f"No item named '{args.name}' found.")
        elif args.command == "search":
            results = commands.search_items(args.query)
            if not results:
                print(f"No items matching '{args.query}'.")
            else:
                _print_table(results)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
