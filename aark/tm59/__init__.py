"""Technical Memorandum 59 2017 (TM59:2017): https://www.cibse.org/knowledge-research/knowledge-portal/technical-memorandum-59-design-methodology-for-the-assessment-of-overheating-risk-in-homes.

Notes
-----
A key user input is `zone_maps` with the conceptual type:

```python
dict[str, dict[str, list[str]]]
```

Each key is a dwelling name, and each value represents a dwelling or a collection of
communal corridors. An example of `zone_maps` is:

```python
zone_maps = {
    "flat_1": {
        "living_kitchen": ["flat_1_living_kitchen"],
        "double_bedroom": ["flat_1_bedroom_1", "flat_1_bedroom_2"],
        "single_bedroom": ["flat_1_bedroom_3"],
        "bathroom": ["flat_1_bathroom"],
        "hall": ["flat_1_hall"],
    },
    "flat_2": {
        "living": ["flat_2_living"],
        "kitchen": ["flat_2_kitchen"],
        "double_bedroom": ["flat_2_bedroom"],
        "bathroom": ["flat_2_bathroom"],
        "hall": ["flat_2_hall"],
    },
    "communal_corridor": {
        "communal_corridor": [
            "corridor_floor_1",
            "corridor_floor_2",
            "corridor_floor_3",
        ]
    },
}
```

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
