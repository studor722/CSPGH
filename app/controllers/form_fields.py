"""Query and form field coercion helpers for HTML GET/POST controllers."""

from app.models import Sex


def blank_to_none(value: str | None) -> str | None:
    """Normalize empty or whitespace-only query values to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def to_int_or_none(value: str | None) -> int | None:
    """Parse an integer query parameter, returning None on blank or invalid text."""
    cleaned = blank_to_none(value)
    if cleaned is None:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def to_sex_or_none(value: str | None) -> Sex | None:
    """Parse a Sex enum query parameter, returning None on blank or unknown values."""
    cleaned = blank_to_none(value)
    if cleaned is None:
        return None
    try:
        return Sex(cleaned.upper())
    except ValueError:
        return None


def to_bool_or_none(value: str | None) -> bool | None:
    """Parse 'true'/'false' strings, returning None on blank or other values."""
    cleaned = blank_to_none(value)
    if cleaned is None:
        return None
    lowered = cleaned.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None

