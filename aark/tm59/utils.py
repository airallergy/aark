"""Utility functions shared by the TM59 module."""

from collections import Counter
from typing import TYPE_CHECKING

import aark.ep.generic
import aark.tm59
from aark.tm59.data import (
    ALL_ROOM_TYPES,
    ANCILLARY_ROOM_TYPES,
    BEDROOM_TYPES,
    COMMUNAL_CORRIDOR_TYPE,
    STUDIO_TYPE,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eppy.modeleditor import IDF

    type ZoneMap = Mapping[str, Sequence[str]]


# -----------------------------------------------------------------------------
# UID generation
# -----------------------------------------------------------------------------


def _uid(*args: str) -> str:
    """Build a standard aark-generated uid."""
    uid = "_".join(arg for arg in args if arg)
    return aark.tm59.prefix(uid)


def gain_uid(gain_type: str, zone_name: str) -> str:
    """Build the uid of a zone-specific internal gain."""
    return _uid(gain_type, zone_name)


def sched_uid(sched_type: str, room_type: str = "") -> str:
    """Build the uid of an internal gain schedule."""
    return _uid(sched_type, room_type)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_zone_map(zone_map: ZoneMap) -> None:
    """Validate the structure of a dwelling or communal corridor zone map."""
    # a zone map must not be empty
    if not zone_map:
        raise ValueError(f"Empty zone map: {zone_map}.")

    # check room types
    room_types = set(zone_map)

    # a room type must be valid
    invalid_room_types = room_types - ALL_ROOM_TYPES
    if invalid_room_types:
        raise ValueError(f"Invalid room types: {invalid_room_types}.")

    for zone_names in zone_map.values():
        # a zone name sequence must not be str or bytes
        if isinstance(zone_names, str):
            raise TypeError(f"Invalid zone sequence: {zone_names}.")

        if len(zone_names) == 0:
            raise ValueError(f"Empty zone sequence: {zone_names}.")

    if COMMUNAL_CORRIDOR_TYPE in room_types:
        # a communal corridor must not co-exist with dwelling room types
        if room_types != {COMMUNAL_CORRIDOR_TYPE}:
            raise ValueError(
                f"Mixed communal corridor and dwelling room types: {room_types}."
            )

    elif STUDIO_TYPE in room_types:
        # a studio must not co-exist with other habitable room types
        if room_types - ({STUDIO_TYPE} | ANCILLARY_ROOM_TYPES):
            raise ValueError(
                f"Mixed studio and other habitable room types: {room_types}."
            )

        # a studio must not contain more than one studio zone
        studio_zone_names = zone_map[STUDIO_TYPE]
        if len(studio_zone_names) > 1:
            raise ValueError(f"Multiple studios: {studio_zone_names}.")

    else:
        n_bedrooms = sum(
            len(zone_map.get(room_type, ())) for room_type in BEDROOM_TYPES
        )

        if n_bedrooms == 0:
            raise ValueError(f"Missing bedrooms: {zone_map}.")


def validate_zone_maps(idf: IDF, zone_maps: Sequence[ZoneMap]) -> None:
    """Validate all zone maps provided by users."""
    # validate the structure of each zone map
    for zone_map in zone_maps:
        validate_zone_map(zone_map)

    # get all zone names
    zone_names = [
        zone_name
        for zone_map in zone_maps
        for zone_names in zone_map.values()
        for zone_name in zone_names
    ]

    # all zone names must be unique across all zone maps
    duplicate_names = sorted(
        name for name, count in Counter(zone_names).items() if count > 1
    )
    if duplicate_names:
        raise ValueError(f"Duplicate zone names: {duplicate_names}.")

    # validate the existence of zone names in the idf
    aark.ep.generic.validate_zones_exist_by_name(idf, zone_names)


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def is_communal_corridor_zone_map(zone_map: ZoneMap) -> bool:
    """Return whether a zone map represents communal corridors."""
    return set(zone_map) == {COMMUNAL_CORRIDOR_TYPE}
