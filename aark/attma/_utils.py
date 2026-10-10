"""Internal utilities for ATTMA methods."""

import aark._utils


def prefix(s: str) -> str:
    """Prepend the ATTMA TSL1 namespace to a string."""
    return aark._utils.prefix(f"attma_tsl1_{s}")


def uid(*args: str) -> str:
    """Build a standard `aark`-generated UID."""
    return prefix("_".join(arg for arg in args if arg))
