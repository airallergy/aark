"""Technical Memorandum 59 2017 (TM59:2017): https://www.cibse.org/knowledge-research/knowledge-portal/technical-memorandum-59-design-methodology-for-the-assessment-of-overheating-risk-in-homes.

Notes
-----
A key user input is `zone_maps` with the conceptual type:

```python
list[dict[str, list[str]]]
```

Each dictionary represents a dwelling or a collection of communal corridors. An example
of `zone_maps` is:

```python
zone_maps = [
    {
        "living_kitchen": ["Flat 1 Living Kitchen"],
        "double_bedroom": ["Flat 1 Bedroom 1", "Flat 1 Bedroom 2"],
        "single_bedroom": ["Flat 1 Bedroom 3"],
        "bathroom": ["Flat 1 Bathroom"],
        "hall": ["Flat 1 Hall"],
    },
    {
        "living": ["Flat 2 Living"],
        "kitchen": ["Flat 2 Kitchen"],
        "double_bedroom": ["Flat 2 Bedroom"],
        "bathroom": ["Flat 2 Bathroom"],
        "hall": ["Flat 2 Hall"],
    },
    {
        "communal_corridor": [
            "Corridor Floor 1",
            "Corridor Floor 2",
            "Corridor Floor 3",
        ]
    },
]
```

The following modelling assumptions are used by `aark` but not explicitly specified by
TM59:

- The lighting gain is applied to all rooms by floor area, including non-habitable rooms
  with neither people nor equipment gain, such as bathrooms and halls.
- Intra-dwelling doors are open when occupants are awake and closed otherwise. All other
  doors are closed.
"""
