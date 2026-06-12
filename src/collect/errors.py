"""Domain-level exceptions, kept free of any CLI/web concerns.

Adapters (cli.py, web app) catch these and translate them into exit codes
or HTTP responses.
"""


class CollectError(Exception):
    """Base class for all domain errors."""


class ValidationError(CollectError):
    """Input failed a domain rule (bad category, malformed date, etc.)."""


class ItemNotFound(CollectError):
    """No item exists with the given id."""


class CategoryError(CollectError):
    """Invalid category operation (duplicate, in-use, unknown)."""
