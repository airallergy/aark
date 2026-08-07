"""airallergy's research kit.

Notes
-----
Checking the equality of IDF field values is complex, because alpha fields are generally
case insensitive and ignore leading and trailing whitespace, with some exceptions.
`eppy` does not handle this well. For simplicity and consistency, `aark` treats the
equality of field values as follows.

- Assumes a valid and internally consistent input IDF.

  - The IDF has no input errors when simulated.
  - For existing objects in the IDF where some reference others by name, the object
    names and their reference names are exactly equal in case and surrounding
    whitespace.

- Looks up field values in the input IDF considering case and surrounding whitespace.

  - Numeric values are compared using approximate equality, except for blank and
    automatic numeric values, which are compared exactly.
  - Alpha values are compared after removing surrounding whitespace.
  - Alpha comparison is case insensitive, unless the field is marked `retaincase` in
    the IDD.

- Deduplicates objects of the same class using exact equality when the same IDF
  instance remains in memory.

  - `aark` adds field values as strings.
  - If an IDF has objects added by `aark` and gets loaded by `eppy` again, `aark` may
    fail because `eppy` may parse numeric strings to floats or ints.

- Fails fast on field-related violations when validating an input IDF.

  - Only the first violation is reported in the error message.
"""

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    type MonthDay = tuple[int, int]

__version__ = "0.1.0"


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


def validate_positive_n_timesteps(n_timesteps: int) -> None:
    """Validate that the number of timesteps is positive."""
    if n_timesteps <= 0:
        raise ValueError(f"Non-positive number of timesteps: {n_timesteps}.")
