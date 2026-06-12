import argparse
import sys

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


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "add":
            commands.add(
                name=args.name,
                category=args.category,
                brand=args.brand,
                acquired=args.acquired,
                value=args.value,
                notes=args.notes,
            )
        elif args.command == "list":
            commands.list_items(category=getattr(args, "category", None))
        elif args.command == "remove":
            commands.remove(args.name)
        elif args.command == "search":
            commands.search(args.query)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
