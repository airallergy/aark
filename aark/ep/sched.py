"""Manipulate EnergyPlus schedule objects."""

import itertools
from typing import TYPE_CHECKING

import aark._utils
import aark.ep.obj
from aark._utils import DAY_NAMES

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.modeleditor import IDF

    from aark._utils import Interval, MonthDay


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
    "Control": {
        "Lower_Limit_Value": "0",
        "Upper_Limit_Value": "4",
        "Numeric_Type": "Discrete",
        "Unit_Type": "Dimensionless",
    },
}
DAY_TYPES = (
    DAY_NAMES[-1],
    *DAY_NAMES[1:-1],
    "Holiday",
    "SummerDesignDay",
    "WinterDesignDay",
    "CustomDay1",
    "CustomDay2",
)


def get_active_val(val_type: str) -> str:
    """Return a conventional active schedule value."""
    if val_type in {"Fraction", "On/Off"}:
        return VAL_TYPE2LIMITS[val_type]["Upper_Limit_Value"]

    raise ValueError(f"Unsupported schedule value type: {val_type}.")


def get_inactive_val(val_type: str, sub_val_type: str = "") -> str:
    """Return a conventional inactive schedule value."""
    if val_type == "Temperature":
        if sub_val_type == "Heating":
            return VAL_TYPE2LIMITS[val_type]["Lower_Limit_Value"]
        elif sub_val_type == "Cooling":
            return VAL_TYPE2LIMITS[val_type]["Upper_Limit_Value"]
    elif val_type in VAL_TYPE2LIMITS:
        return VAL_TYPE2LIMITS[val_type]["Lower_Limit_Value"]

    raise ValueError(
        f"Unsupported schedule value type and subtype: {val_type}, {sub_val_type}."
    )


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


def add_type_limits_obj(idf: IDF, val_type: str) -> None:
    """Add a schedule type limits object if it is absent."""
    # validate the schedule value type
    if val_type not in VAL_TYPE2LIMITS:
        raise ValueError(f"Unknown schedule value type: {val_type}.")

    # add the schedule type limits object
    aark.ep.obj.add(
        idf,
        "ScheduleTypeLimits",
        Name=aark._utils.prefix(val_type),
        **VAL_TYPE2LIMITS[val_type],
    )


# -----------------------------------------------------------------------------
# Day-week-year
# -----------------------------------------------------------------------------


def add_day_obj(
    idf: IDF, obj_name: str, val_type: str, hourly_vals: Sequence[str]
) -> None:
    """Add a `Schedule:Day:Hourly` object if it is absent."""
    if len(hourly_vals) != 24:
        raise ValueError(f"Invalid length for 24 hourly values: {len(hourly_vals)}.")

    # add the schedule type limits object
    add_type_limits_obj(idf, val_type)

    # add the day schedule object
    obj_fields = {
        "Name": obj_name,
        "Schedule_Type_Limits_Name": aark._utils.prefix(val_type),
    }
    for i, val in enumerate(hourly_vals, start=1):
        obj_fields[f"Hour_{i}"] = val

    aark.ep.obj.add(idf, "Schedule:Day:Hourly", **obj_fields)


def add_week_obj(idf: IDF, obj_name: str, **day_type2obj_name: str) -> None:
    """Add a `Schedule:Week:Daily` object if it is absent."""
    obj_fields = {"Name": obj_name}
    for day_type, day_obj_name in day_type2obj_name.items():
        obj_fields[f"{day_type}_ScheduleDay_Name"] = day_obj_name

    aark.ep.obj.add(idf, "Schedule:Week:Daily", **obj_fields)


def add_year_obj(
    idf: IDF, obj_name: str, val_type: str, *blocks: Interval[str]
) -> None:
    """Add a `Schedule:Year` object if it is absent."""
    # add the schedule type limits object
    add_type_limits_obj(idf, val_type)

    # add the year schedule object
    obj_fields = {
        "Name": obj_name,
        "Schedule_Type_Limits_Name": aark._utils.prefix(val_type),
    }
    for i, (start_month_day, end_month_day, week_obj_name) in enumerate(
        blocks, start=1
    ):
        start_month, start_day = start_month_day
        end_month, end_day = end_month_day

        obj_fields |= {
            f"ScheduleWeek_Name_{i}": week_obj_name,
            f"Start_Month_{i}": str(start_month),
            f"Start_Day_{i}": str(start_day),
            f"End_Month_{i}": str(end_month),
            f"End_Day_{i}": str(end_day),
        }
    aark.ep.obj.add(idf, "Schedule:Year", **obj_fields)


# -----------------------------------------------------------------------------
# Compact
# -----------------------------------------------------------------------------


def make_compact_block(
    end_month_day: MonthDay, *day_profiles: tuple[str, Sequence[str]]
) -> list[str]:
    """Create one `Through` block from ordered `(day_type, hourly_vals)` pairs."""
    month, day = end_month_day

    fields = [f"Through: {month:02d}/{day:02d}"]
    for day_type, hourly_vals in day_profiles:
        fields.append(f"For: {day_type}")

        for end_hour, val in compress_hourly_vals(hourly_vals):
            fields.extend((f"Until: {end_hour:02d}:00", val))

    return fields


def add_compact_obj(
    idf: IDF, obj_name: str, val_type: str, *blocks: Sequence[str]
) -> None:
    """Add a `Schedule:Compact` object if it is absent."""
    # validate the blocks
    if not blocks:
        raise ValueError(f"No compact schedule block: {blocks}.")

    if any(not block for block in blocks):
        raise ValueError(f"Empty compact schedule blocks: {blocks}.")

    # add the schedule type limits object
    add_type_limits_obj(idf, val_type)

    # add the compact schedule object
    obj_fields = {
        "Name": obj_name,
        "Schedule_Type_Limits_Name": aark._utils.prefix(val_type),
    }
    for i, val in enumerate(list(itertools.chain(*blocks)), start=1):
        obj_fields[f"Field_{i}"] = val

    aark.ep.obj.add(idf, "Schedule:Compact", **obj_fields)


# -----------------------------------------------------------------------------
# Constant
# -----------------------------------------------------------------------------


def add_constant_obj(idf: IDF, obj_name: str, val_type: str, val: str) -> None:
    """Add a `Schedule:Constant` object if it is absent."""
    # add the schedule type limits object
    add_type_limits_obj(idf, val_type)

    # add the constant schedule object
    aark.ep.obj.add(
        idf,
        "Schedule:Constant",
        Name=obj_name,
        Schedule_Type_Limits_Name=aark._utils.prefix(val_type),
        Hourly_Value=val,
    )
