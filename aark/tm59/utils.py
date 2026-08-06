"""Utility functions shared by the TM59 module."""

from typing import TYPE_CHECKING

import aark.tm59
from aark.tm59.data import ALL_ROOM_TYPES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    type RoomMap = Mapping[str, Sequence[str]]


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


def validate_room_map(room_map: RoomMap) -> None:
    """Validate the structure of a room map."""
    # a room map must not be empty
    if not room_map:
        raise ValueError(f"Empty room map: {room_map}.")

    # check room types
    room_types = set(room_map)

    # a room type must be valid
    invalid_room_types = room_types - ALL_ROOM_TYPES
    if invalid_room_types:
        raise ValueError(f"Invalid room types: {invalid_room_types}.")

    for obj_names in room_map.values():
        # an object name sequence must not be str
        if isinstance(obj_names, str):
            raise TypeError(f"Invalid object name sequence: {obj_names}.")

        if len(obj_names) == 0:
            raise ValueError(f"Empty object name sequence: {obj_names}.")
