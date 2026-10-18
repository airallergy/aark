"""Utility functions shared by TM59 modules."""

import datetime as dt
import re
from typing import TYPE_CHECKING

import aark._utils
import aark.ep.sched
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.tm59.data import ALL_ROOM_TYPES

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from aark._utils import MonthDay

    type RoomMap = Mapping[str, Sequence[str]]


def make_compact_blocks(
    hourly_vals: Sequence[str],
    start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    end_month_day: MonthDay = YEAR_END_MONTH_DAY,
) -> list[list[str]]:
    """Create compact schedule blocks with zero values outside an active period."""
    # parse and validate two dates
    start_date = aark._utils.as_date(start_month_day)
    end_date = aark._utils.as_date(end_month_day)

    if start_date > end_date:
        raise ValueError(
            f"Start month-day must not be after end month-day: {start_month_day}, {end_month_day}."
        )

    zero_hourly_vals = ("0",) * 24
    blocks = []

    if start_date != aark._utils.as_date(YEAR_START_MONTH_DAY):
        inactive_end_date = start_date - dt.timedelta(days=1)
        blocks.append(
            aark.ep.sched.make_compact_block(
                (inactive_end_date.month, inactive_end_date.day),
                ("AllDays", zero_hourly_vals),
            )
        )

    blocks.append(
        aark.ep.sched.make_compact_block(
            (end_date.month, end_date.day), ("AllDays", hourly_vals)
        )
    )

    if end_date != aark._utils.as_date(YEAR_END_MONTH_DAY):
        blocks.append(
            aark.ep.sched.make_compact_block(
                YEAR_END_MONTH_DAY, ("AllDays", zero_hourly_vals)
            )
        )

    return blocks


# -----------------------------------------------------------------------------
# UID generation
# -----------------------------------------------------------------------------


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    return aark._utils.prefix(f"tm59_{s}")


def _uid(*args: str) -> str:
    """Build a standard `aark`-generated UID."""
    return prefix("_".join(arg for arg in args if arg))


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

    room_types = set(room_map)

    # a room type must be valid
    invalid_room_types = room_types - ALL_ROOM_TYPES
    if invalid_room_types:
        raise ValueError(f"Invalid room types: {invalid_room_types}.")

    for obj_names in room_map.values():
        # an object name sequence must not be `str`
        if isinstance(obj_names, str):
            raise TypeError(f"Invalid object name sequence: {obj_names}.")

        # an object name sequence must not be empty
        if not obj_names:
            raise ValueError(f"Empty object name sequence: {obj_names}.")
