"""Internal utilities shared across `aark`."""

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    type MonthDay = tuple[int, int]


LEAP_REF_YEAR = 2000
NON_LEAP_REF_YEAR = 1995
YEAR_START_MONTH_DAY = (1, 1)
YEAR_END_MONTH_DAY = (12, 31)


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    if not s:
        raise ValueError(f"Empty string: {s}.")

    if s.upper().startswith(__package__.upper()):
        raise ValueError(f"String already has a {__package__} prefix: {s}.")

    return f"{__package__}_{s}"


def as_date(month_day: MonthDay, year: int = LEAP_REF_YEAR) -> dt.date:
    """Convert a month-day to a date, using the reference leap year by default."""
    return dt.date(year, *month_day)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_n_timesteps(n_timesteps: int) -> None:
    """Validate that the number of timesteps is positive."""
    if n_timesteps <= 0:
        raise ValueError(f"Non-positive number of timesteps: {n_timesteps}.")


def validate_subperiod(
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    min_start_month_day: MonthDay,
    max_end_month_day: MonthDay,
) -> None:
    """Validate that a period lies within a permitted period."""
    if not (
        as_date(min_start_month_day)
        <= as_date(start_month_day)
        <= as_date(end_month_day)
        <= as_date(max_end_month_day)
    ):
        raise ValueError(
            f"Invalid assessment period: {start_month_day}, {end_month_day}."
        )
