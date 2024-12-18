from ember_agents.settings import SETTINGS


def format_currency_string(amount_str: str, decimal_places: int = 2) -> str:
    """Format a currency string to a specified number of decimal places with thousands separators.

    Args:
        amount_str: String representation of a number
        decimal_places: Number of decimal places to round to (default 2)

    Returns:
        Formatted string with specified decimal places and thousands separators
        Example: "1234.5" -> "1,234.50"
    """
    try:
        # The ',' flag adds thousands separators
        return f"{float(amount_str):,.{decimal_places}f}"
    except ValueError as e:
        raise ValueError(f"Invalid currency amount: {amount_str}") from e


def format_metric_suffix(number: str | int | float | None) -> str | None:
    """Format numbers using metric suffix notation (K, M, B, T).

    Args:
        number: A number as string, int, or float

    Returns:
        Formatted string with appropriate metric suffix (K, M, B, T)
        Examples: 1234 -> "1.2K", "1234567" -> "1.2M"
    """
    if number is None:
        return None

    try:
        # Convert to float if string, otherwise use directly
        num = float(number) if isinstance(number, str) else float(number)

        if num < 1000:  # noqa: PLR2004
            return f"{num:.1f}"
        elif num < 1_000_000:  # noqa: PLR2004
            return f"{num/1000:.1f}K"
        elif num < 1_000_000_000:  # noqa: PLR2004
            return f"{num/1_000_000:.1f}M"
        elif num < 1_000_000_000_000:  # noqa: PLR2004
            return f"{num/1_000_000_000:.1f}B"
        else:
            return f"{num/1_000_000_000_000:.1f}T"

    except (ValueError, TypeError) as e:
        msg = f"Invalid number input: {number}"
        raise ValueError(msg) from e


def format_transaction_url(transaction_url: str) -> str:
    """Formats the transaction url for signing."""

    if SETTINGS.disable_transaction_signing_url:
        return "tap-to-edit-text.com... Oops, work in progress ;)"
    return f"**[Sign here]({transaction_url})** to complete your transaction."
