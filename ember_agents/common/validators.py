from typing import Annotated

from pydantic import AfterValidator


def is_positive_amount(v: str) -> str:
    """Validates number contained in string is positive"""

    assert float(v) > 0, f"Amount {v} is not positive."
    return v


PositiveAmount = Annotated[str, AfterValidator(is_positive_amount)]
