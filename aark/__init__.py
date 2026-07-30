"""airallergy's research kit."""

__version__ = "0.1.0"


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    if not s:
        raise ValueError(f"Empty string: {s}.")

    if s.casefold().startswith(__package__.casefold()):
        raise ValueError(f"String already has a {__package__} prefix: {s}.")

    return f"{__package__}_{s}"
