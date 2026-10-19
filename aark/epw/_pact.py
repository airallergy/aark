"""Validate `aark` requirements about EnergyPlus weather data structures."""

from typing import TYPE_CHECKING

import aark.epw._utils

if TYPE_CHECKING:
    from typing import TextIO


def validate_full_year_hourly(f: TextIO) -> None:
    """Validate full-year hourly line counts."""
    n_lines = len(aark.epw._utils.read_lines(f))

    if n_lines not in {8768, 8792}:
        raise ValueError(f"Expected 8768 or 8792 lines: {n_lines}.")
