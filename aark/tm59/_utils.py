"""Utility functions shared by TM59 modules."""

import re
from collections import Counter
from typing import TYPE_CHECKING

import aark._utils
import aark.ep.obj
from aark.tm59.data import ALL_ROOM_TYPES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eppy.modeleditor import IDF

    type RoomMap = Mapping[str, Sequence[str]]


# -----------------------------------------------------------------------------
# UID generation
# -----------------------------------------------------------------------------


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    p = aark._utils.prefix("tm59_")

    if not s:
        raise ValueError(f"Empty string: {s}.")

    if s.upper().startswith(p.upper()):
        raise ValueError(f"Prefix already exists: {s}.")

    return f"{p}{s}"


def _uid(*args: str) -> str:
    """Build a standard `aark`-generated UID."""
    args = tuple(arg for arg in args if arg)

    if not args:
        raise ValueError(f"Empty UID arguments: {args}.")

    return prefix("_".join(args))


def gain_uid(gain_type: str, zone_name: str) -> str:
    """Build the UID of a zone-specific internal gain."""
    return _uid(gain_type, zone_name)


def sched_uid(sched_type: str, room_type: str = "") -> str:
    """Build the UID of an internal gain schedule."""
    return _uid(sched_type, room_type)


def erl_uid(kind: str, src_name: str) -> str:
    """Build an ERL-compatible UID."""
    _src_name = src_name

    if any(char.isspace() for char in src_name):
        src_name = "".join(part[:1].upper() + part[1:] for part in src_name.split())

    src_name = re.sub(r"[^A-Za-z0-9_]", "", src_name)

    if not src_name:
        raise ValueError(f"Invalid source name: {_src_name}.")

    return _uid(kind, src_name)


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
        # an object name sequence must not be `str`
        if isinstance(obj_names, str):
            raise TypeError(f"Invalid object name sequence: {obj_names}.")

        if len(obj_names) == 0:
            raise ValueError(f"Empty object name sequence: {obj_names}.")


def validate_mapped_obj_names(idf: IDF, cls_name: str, *room_maps: RoomMap) -> None:
    """Validate that mapped object names are unique and exist in the IDF."""
    # get all mapped object names
    obj_names = [
        name for room_map in room_maps for names in room_map.values() for name in names
    ]

    # all object names must be unique
    duplicate_names = sorted(name for name, n in Counter(obj_names).items() if n > 1)
    if duplicate_names:
        raise ValueError(f"Duplicate {cls_name} object names: {duplicate_names}.")

    # all object names must exist in the idf
    for obj_name in obj_names:
        aark.ep.obj.get_named(idf, cls_name, obj_name)
