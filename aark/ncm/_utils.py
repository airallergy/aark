"""Utility functions shared by NCM modules."""

import datetime as dt
from typing import TYPE_CHECKING

import aark._utils
import aark.ep.obj
import aark.ep.sched
import aark.ncm.data.activity
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.ep.sched import DAY_TYPES
from aark.ncm.data import ACTIVITY_DATABASE

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.ncm.data.activity import AnnualScheds, DailyScheds, WeeklyScheds

    type ActivityMap = Mapping[str, Sequence[str]]


# -----------------------------------------------------------------------------
# UID generation
# -----------------------------------------------------------------------------


def prefix(s: str) -> str:
    """Prepend the package namespace to a string."""
    return aark._utils.prefix(f"ncm_{s}")


def _uid(*args: str) -> str:
    """Build a standard `aark`-generated UID."""
    return prefix("_".join(arg for arg in args if arg))


def gain_uid(gain_type: str, zone_name: str) -> str:
    """Build the UID of a zone-specific internal gain."""
    return _uid(gain_type, zone_name)


def sched_uid(sched_type: str, activity_name: str = "") -> str:
    """Build the UID of a generated schedule."""
    return _uid(sched_type, activity_name)


# -----------------------------------------------------------------------------
# Schedule construction
# -----------------------------------------------------------------------------


def mask_endpoints(
    endpoints: Sequence[tuple[MonthDay, str]],
    inactive_val: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> list[tuple[MonthDay, str]]:
    """Order full-year endpoints and replace items outside the active period."""
    _validate_endpoints(endpoints)

    endpoints = list(endpoints)

    # insert endpoints at the active period boundaries
    end_month_days = {month_day for month_day, _ in endpoints}
    if end_month_day not in end_month_days:
        endpoints.append((end_month_day, ""))
        end_month_days.add(end_month_day)

    if start_month_day > YEAR_START_MONTH_DAY:
        prev_date = aark._utils.as_date(start_month_day) - dt.timedelta(days=1)
        prev_month_day = (prev_date.month, prev_date.day)

        if prev_month_day not in end_month_days:
            endpoints.append((prev_month_day, ""))

    # sort endpoints chronologically
    endpoints.sort(key=lambda x: x[0])

    # backward fill placeholders
    for i in range(-2, -len(endpoints) - 1, -1):
        month_day, val = endpoints[i]

        if val == "":
            _, val = endpoints[i + 1]
            endpoints[i] = (month_day, val)

    # replace values outside the active period
    masked_endpoints = []
    for month_day, val in endpoints:
        if start_month_day <= end_month_day:
            active = start_month_day <= month_day <= end_month_day
        else:
            active = (month_day >= start_month_day) or (month_day <= end_month_day)

        masked_endpoints.append((month_day, val if active else inactive_val))

    return masked_endpoints


def expand_endpoints(
    endpoints: Sequence[tuple[MonthDay, str]],
) -> list[tuple[MonthDay, MonthDay, str]]:
    """Expand full-year endpoints into inclusive intervals from 1 January."""
    _validate_endpoints(endpoints)

    start_date = aark._utils.as_date(YEAR_START_MONTH_DAY)

    intervals = []
    for end_month_day, val in sorted(endpoints, key=lambda x: x[0]):
        end_date = aark._utils.as_date(end_month_day)

        intervals.append(((start_date.month, start_date.day), end_month_day, val))
        start_date = end_date + dt.timedelta(days=1)

    return intervals


def add_scheds(
    idf: IDF,
    daily_scheds: DailyScheds,
    weekly_scheds: WeeklyScheds,
    annual_scheds: AnnualScheds,
    val_type: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    setpoint: str = "",
) -> None:
    """Add schedules for one annual profile.

    Temperature schedules must cover a full calendar year.
    """
    if (val_type == "Temperature") and (
        (start_month_day != YEAR_START_MONTH_DAY)
        or (end_month_day != YEAR_END_MONTH_DAY)
    ):
        raise ValueError(
            f"Temperature schedules must cover a full calendar year: {start_month_day}, {end_month_day}."
        )

    # infer the schedule value subtype
    (annual_sched_name,) = annual_scheds
    sub_val_type = aark.ncm.data.activity.get_sub_val_type(annual_sched_name)

    # get the inactive value
    inactive_val = aark.ep.sched.get_inactive_val(val_type, sub_val_type)

    # set the fixed design and custom day values
    if val_type == "Temperature":
        winter_design_val = summer_design_val = custom_day_val = setpoint
    else:
        winter_design_val = custom_day_val = inactive_val
        summer_design_val = aark.ep.sched.get_active_val(val_type)

    # add the inactive day schedule
    suffix = f"{val_type.lower()}"
    if sub_val_type:
        suffix += f"_{sub_val_type.lower()}"
    inactive_day_sched_obj_name = prefix(f"daily_inactive_{suffix}")

    if (val_type != "Temperature") or (setpoint == inactive_val):
        aark.ep.sched.add_type_limits_obj(idf, val_type)
        aark.ep.obj.add(
            idf,
            "Schedule:Day:Interval",
            Name=inactive_day_sched_obj_name,
            Schedule_Type_Limits_Name=aark._utils.prefix(val_type),
            Interpolate_to_Timestep="No",
            Time_1="Until: 24:00",
            Value_Until_Time_1=inactive_val,
        )

    # add constant design and custom day schedules
    special_day_type2sched_obj_name = {}
    for day_type, val in (
        ("SummerDesignDay", summer_design_val),
        ("WinterDesignDay", winter_design_val),
        ("CustomDay1", custom_day_val),
        ("CustomDay2", custom_day_val),
    ):
        if val == inactive_val:
            day_sched_obj_name = inactive_day_sched_obj_name
        else:
            if val_type == "Temperature":
                day_sched_obj_name = prefix(f"daily_constant_setpoint_{val}")
            else:
                day_sched_obj_name = prefix(f"daily_constantly_active_{suffix}")

            aark.ep.sched.add_day_obj(idf, day_sched_obj_name, val_type, (val,) * 24)

        special_day_type2sched_obj_name[day_type] = day_sched_obj_name

    # add the inactive week schedule
    if val_type != "Temperature":
        inactive_week_sched_obj_name = prefix(f"weekly_inactive_{suffix}")

        aark.ep.obj.add(
            idf,
            "Schedule:Week:Compact",
            Name=inactive_week_sched_obj_name,
            DayType_List_1="SummerDesignDay",
            ScheduleDay_Name_1=special_day_type2sched_obj_name["SummerDesignDay"],
            DayType_List_2="WinterDesignDay",
            ScheduleDay_Name_2=special_day_type2sched_obj_name["WinterDesignDay"],
            DayType_List_3="CustomDay1 CustomDay2",
            ScheduleDay_Name_3=special_day_type2sched_obj_name["CustomDay1"],
            DayType_List_4="AllOtherDays",
            ScheduleDay_Name_4=inactive_day_sched_obj_name,
        )

    # add other day schedules
    for daily_sched_name, hourly_vals in daily_scheds.items():
        day_sched_obj_name = prefix(daily_sched_name)

        aark.ep.sched.add_day_obj(idf, day_sched_obj_name, val_type, hourly_vals)

    # add other week schedules
    for weekly_sched_name, day2sched_name in weekly_scheds.items():
        week_sched_obj_name = prefix(weekly_sched_name)

        day_type2obj_name = {}
        for day_type in DAY_TYPES:
            if day_type in special_day_type2sched_obj_name:
                day_type2obj_name[day_type] = special_day_type2sched_obj_name[day_type]
            else:
                day_type2obj_name[day_type] = prefix(day2sched_name[day_type])

        aark.ep.sched.add_week_obj(idf, week_sched_obj_name, **day_type2obj_name)

    # add the year schedule
    year_sched_obj_name = prefix(annual_sched_name)
    weekly_sched_endpoints = annual_scheds[annual_sched_name]

    week_sched_endpoints = [
        (end_month_day, prefix(weekly_sched_name))
        for end_month_day, weekly_sched_name in weekly_sched_endpoints
    ]
    if val_type != "Temperature":
        week_sched_endpoints = mask_endpoints(
            week_sched_endpoints,
            inactive_week_sched_obj_name,
            start_month_day,
            end_month_day,
        )
    year_sched_blocks = expand_endpoints(week_sched_endpoints)
    aark.ep.sched.add_year_obj(idf, year_sched_obj_name, val_type, *year_sched_blocks)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_activity_map(activity_map: ActivityMap) -> None:
    """Validate the structure of an activity map."""
    # an activity map must not be empty
    if not activity_map:
        raise ValueError(f"Empty activity map: {activity_map}.")

    activity_names = set(activity_map)
    all_activity_names = ACTIVITY_DATABASE.get_activity_names()

    # activity names must exist in the database
    invalid_activity_names = activity_names - set(all_activity_names)
    if invalid_activity_names:
        raise ValueError(f"Invalid activity names: {invalid_activity_names}.")

    for obj_names in activity_map.values():
        # an object name sequence must not be `str`
        if isinstance(obj_names, str):
            raise TypeError(f"Invalid object name sequence: {obj_names}.")

        # an object name sequence must not be empty
        if not obj_names:
            raise ValueError(f"Empty object name sequence: {obj_names}.")


def validate_zone_map(idf: IDF, zone_map: ActivityMap) -> None:
    """Validate one activity-to-zone map."""
    # the zone map must have a valid structure
    validate_activity_map(zone_map)

    # mapped zone names must be unique and identify objects in the idf
    zone_names = [name for names in zone_map.values() for name in names]
    aark.ep.obj.validate_obj_names(idf, "Zone", *zone_names)


def _validate_endpoints(endpoints: Sequence[tuple[MonthDay, str]]) -> None:
    """Validate unique full-year endpoints with non-empty values."""
    vals = {val for _, val in endpoints}
    end_month_days = {month_day for month_day, _ in endpoints}

    # endpoint values must be non-empty
    if "" in vals:
        raise ValueError(f"Endpoint value cannot be empty string: {endpoints}.")

    # endpoint month-day pairs must be unique
    if len(end_month_days) != len(endpoints):
        raise ValueError(f"Duplicate endpoint month-day pairs: {endpoints}.")

    # endpoints must include 31 december
    if YEAR_END_MONTH_DAY not in end_month_days:
        raise ValueError(f"Missing (12, 31) endpoint: {endpoints}.")
