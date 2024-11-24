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


def format_transaction_url(transaction_url: str) -> str:
    """Formats the transaction url for signing."""

    if SETTINGS.disable_transaction_signing_url:
        return "tap-to-edit-text.com"
    return f"**[Sign here]({transaction_url})**"
