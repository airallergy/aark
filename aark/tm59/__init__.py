"""Technical Memorandum 59 2017 (TM59:2017): https://www.cibse.org/knowledge-research/knowledge-portal/technical-memorandum-59-design-methodology-for-the-assessment-of-overheating-risk-in-homes.

Notes
-----
The following modelling assumptions are used by `aark` but not explicitly specified by
TM59:

- The lighting gain is applied to all rooms by floor area, including non-habitable rooms
  with neither people nor equipment gain, such as bathrooms and halls.
- Intra-dwelling doors are open when occupants are awake and closed otherwise. All other
  doors are closed.
"""

import aark


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    p = aark.prefix("tm59_")

    if not s:
        raise ValueError(f"Empty string: {s}.")

    if s.upper().startswith(p.upper()):
        raise ValueError(f"String already has a {p} prefix: {s}.")

    return f"{p}{s}"
