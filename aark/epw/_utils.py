"""Internal utilities shared across EnergyPlus weather operations."""

from typing import TYPE_CHECKING

import aark._utils

if TYPE_CHECKING:
    from typing import TextIO


def read_lines(f: TextIO) -> list[str]:
    """Read from the beginning, omitting trailing blank lines."""
    f.seek(0)
    lines = f.readlines()

    while lines and not lines[-1].strip():
        lines.pop()

    return lines


# -----------------------------------------------------------------------------
# UID generation
# -----------------------------------------------------------------------------


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    return aark._utils.prefix(f"epw_{s}")
