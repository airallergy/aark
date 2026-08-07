"""Manipulate EnergyPlus schedule objects."""

import datetime as dt
import itertools
from typing import TYPE_CHECKING

import aark.ep.generic

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.modeleditor import IDF

    from aark import MonthDay


VAL_TYPE2LIMITS = {
    "Fraction": {
        "Lower_Limit_Value": "0",
        "Upper_Limit_Value": "1",
        "Numeric_Type": "Continuous",
        "Unit_Type": "Dimensionless",
    },
    "On/Off": {
        "Lower_Limit_Value": "0",
        "Upper_Limit_Value": "1",
        "Numeric_Type": "Discrete",
        "Unit_Type": "Availability",
    },
    "Temperature": {
        "Lower_Limit_Value": "-100",
        "Upper_Limit_Value": "100",
        "Numeric_Type": "Continuous",
        "Unit_Type": "Temperature",
    },
    "Metabolism": {
        "Lower_Limit_Value": "0",
        "Upper_Limit_Value": "",
        "Numeric_Type": "Continuous",
        "Unit_Type": "ActivityLevel",
    },
}


def compress_hourly_vals(hourly_vals: Sequence[str]) -> list[tuple[int, str]]:
    """Merge consecutive equal hourly values."""
    if len(hourly_vals) != 24:
        raise ValueError(f"Invalid length for 24 hourly values: {len(hourly_vals)}.")

    compressed = []
    end_hour = 0

    for val, group in itertools.groupby(hourly_vals):
        end_hour += sum(1 for _ in group)
        compressed.append((end_hour, val))

    return compressed


def make_compact_block(through: MonthDay, hourly_vals: Sequence[str]) -> list[str]:
    """Create one `Through` block for a compact schedule."""
    month, day = through

    fields = [f"Through: {month:02d}/{day:02d}", "For: AllDays"]
    for end_hour, val in compress_hourly_vals(hourly_vals):
        fields.extend((f"Until: {end_hour:02d}:00", val))

    return fields


def make_compact_blocks(
    hourly_vals: Sequence[str],
    start_month_day: MonthDay = (1, 1),
    end_month_day: MonthDay = (12, 31),
) -> list[list[str]]:
    """Create compact schedule blocks with zero values outside an active period."""
    # parse and validate two dates
    start_date = aark.as_date(start_month_day)
    end_date = aark.as_date(end_month_day)

    if start_date > end_date:
        raise ValueError(
            f"Start month-day must not be after end month-day: {start_month_day}, {end_month_day}."
        )

    zero_hourly_vals = ("0",) * 24
    blocks = []

    if start_date != aark.as_date((1, 1)):
        inactive_end_date = start_date - dt.timedelta(days=1)
        blocks.append(
            make_compact_block(
                (inactive_end_date.month, inactive_end_date.day), zero_hourly_vals
            )
        )

    blocks.append(make_compact_block((end_date.month, end_date.day), hourly_vals))

    if end_date != aark.as_date((12, 31)):
        blocks.append(make_compact_block((12, 31), zero_hourly_vals))

    return blocks


def add_type_limits_obj(idf: IDF, val_type: str) -> None:
    """Add a schedule type limits object if it is absent."""
    # validate the schedule value type
    if val_type not in VAL_TYPE2LIMITS:
        raise ValueError(f"Unknown schedule value type: {val_type}.")

    # add the schedule type limits object
    aark.ep.generic.add_obj(
        idf,
        "ScheduleTypeLimits",
        Name=aark.prefix(val_type),
        **VAL_TYPE2LIMITS[val_type],
    )


def add_compact_obj(idf: IDF, name: str, val_type: str, *blocks: Sequence[str]) -> None:
    """Add a compact schedule object if it is absent."""
    # validate the blocks
    if not blocks:
        raise ValueError(f"No compact schedule block: {name}.")

    if any(not block for block in blocks):
        raise ValueError(f"Empty compact schedule blocks: {blocks}.")

    # add the schedule type limits object
    add_type_limits_obj(idf, val_type)

    # add the compact schedule object
    obj_fields = {"Name": name, "Schedule_Type_Limits_Name": aark.prefix(val_type)}
    for i, val in enumerate(list(itertools.chain(*blocks)), start=1):
        obj_fields[f"Field_{i}"] = val

    aark.ep.generic.add_obj(idf, "Schedule:Compact", **obj_fields)
