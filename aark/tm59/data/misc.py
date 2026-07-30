"""Miscellaneous CIBSE TM59:2017 data."""

# unit types
COMMUNAL_CORRIDOR_TYPE = "communal_corridor"
STUDIO_TYPE = "studio"
BEDROOM_TYPES = frozenset({"single_bedroom", "double_bedroom"})
N_BEDROOMS_DEPENDENT_ROOM_TYPES = frozenset({"living_kitchen", "living", "kitchen"})
HABITABLE_ROOM_TYPES = (
    BEDROOM_TYPES | N_BEDROOMS_DEPENDENT_ROOM_TYPES | frozenset({STUDIO_TYPE})
)
ANCILLARY_ROOM_TYPES = frozenset({"bathroom", "hall"})
DWELLING_ROOM_TYPES = HABITABLE_ROOM_TYPES | ANCILLARY_ROOM_TYPES
ALL_ROOM_TYPES = DWELLING_ROOM_TYPES | frozenset({COMMUNAL_CORRIDOR_TYPE})
MAX_TABULATED_N_BEDROOMS = 3
