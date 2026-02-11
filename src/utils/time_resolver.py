"""Resolve natural language date expressions in Spanish to ISO date strings."""

import dateparser


def resolve_date(text: str, timezone: str = "Europe/Madrid") -> str | None:
    """Parse a Spanish date expression and return ISO format (YYYY-MM-DD) or None."""
    result = dateparser.parse(
        text,
        languages=["es"],
        settings={
            "TIMEZONE": timezone,
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DATES_FROM": "future",
        },
    )
    if result:
        return result.strftime("%Y-%m-%d")
    return None
