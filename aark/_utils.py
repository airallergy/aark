"""Internal utilities shared across `aark`."""

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    type MonthDay = tuple[int, int]
    type Endpoint[T] = tuple[MonthDay, T]
    type Interval[T] = tuple[MonthDay, MonthDay, T]


LEAP_REF_YEAR = 2000
NON_LEAP_REF_YEAR = 1995
YEAR_START_MONTH_DAY = (1, 1)
YEAR_END_MONTH_DAY = (12, 31)
DAY_NAMES = (
    "",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
MONTH_ABBRS = (
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    return f"{__package__}_{s}"


def as_date(month_day: MonthDay, year: int = LEAP_REF_YEAR) -> dt.date:
    """Convert a month-day to a date, using the reference leap year by default."""
    return dt.date(year, *month_day)


def expand_endpoints[T](
    endpoints: Sequence[Endpoint[T]], year: int = LEAP_REF_YEAR
) -> list[Interval[T]]:
    """Expand full-year endpoints into inclusive intervals from 1 January."""
    validate_endpoints(*endpoints)

    start_date = as_date(YEAR_START_MONTH_DAY, year)

    intervals = []
    for end_month_day, val in sorted(endpoints, key=lambda x: x[0]):
        end_date = as_date(end_month_day, year)

        intervals.append(((start_date.month, start_date.day), end_month_day, val))
        start_date = end_date + dt.timedelta(days=1)

    return intervals


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_month_days(*month_days: MonthDay) -> None:
    """Validate month-day pairs using the reference leap year."""
    for month_day in month_days:
        as_date(month_day)


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


def validate_endpoints[T](*endpoints: Endpoint[T]) -> None:
    """Validate unique full-year endpoints."""
    end_month_days = {month_day for month_day, _ in endpoints}

    # endpoint month-day pairs must be unique
    if len(end_month_days) != len(endpoints):
        raise ValueError(f"Duplicate endpoint month-day pairs: {endpoints}.")

    # endpoints must include 31 december
    if YEAR_END_MONTH_DAY not in end_month_days:
        raise ValueError(f"Missing (12, 31) endpoint: {endpoints}.")
