"""airallergy's research kit."""

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    type MonthDay = tuple[int, int]

__version__ = "0.1.0"


LEAP_REF_YEAR = 2000


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    if not s:
        raise ValueError(f"Empty string: {s}.")

    if s.casefold().startswith(__package__.casefold()):
        raise ValueError(f"String already has a {__package__} prefix: {s}.")

    return f"{__package__}_{s}"


def as_date(month_day: MonthDay) -> dt.date:
    """Convert a month-day to a date in a reference leap year."""
    return dt.date(LEAP_REF_YEAR, *month_day)
