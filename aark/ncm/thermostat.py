"""NCM heating and cooling profiles."""

from typing import TYPE_CHECKING

import eppy.bunchhelpers

import aark._utils
import aark.ep._pact
import aark.ep.obj
import aark.ep.sched
import aark.ncm._utils
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.ncm.data import ACTIVITY_DATABASE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.ncm._utils import ActivityMap


def _add_setpoint_scheds(idf: IDF, setpoint_sched_name: str, setpoint: str) -> None:
    """Add setpoint schedules to the IDF."""
    # get ncm data
    daily_scheds, weekly_scheds, annual_scheds = ACTIVITY_DATABASE.get_sched(
        setpoint_sched_name
    )

    # add schedule objects
    aark.ncm._utils.add_scheds(
        idf,
        daily_scheds,
        weekly_scheds,
        annual_scheds,
        "Temperature",
        YEAR_START_MONTH_DAY,
        YEAR_END_MONTH_DAY,
        setpoint,
    )


def _add_avail(
    idf: IDF,
    avail_sched_obj_name: str,
    avail_field_paths: Sequence[tuple[str, str, str]],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    design_day_type: str,
) -> None:
    """Add an availability schedule and assign it to the specified fields."""
    # mask availability values outside the active period
    sched_endpoints = aark.ncm._utils.mask_endpoints(
        [(YEAR_END_MONTH_DAY, "1")], "0", start_month_day, end_month_day
    )

    # build the compact availability schedule
    special_day_profiles = []
    for day_type in ("SummerDesignDay", "WinterDesignDay", "CustomDay1", "CustomDay2"):
        val = "1" if day_type == design_day_type else "0"
        special_day_profiles.append((day_type, (val,) * 24))

    sched_blocks = []
    for month_day, val in sched_endpoints:
        sched_blocks.append(
            aark.ep.sched.make_compact_block(
                month_day, *special_day_profiles, ("AllOtherDays", (val,) * 24)
            )
        )

    # add the availability schedule object
    aark.ep.sched.add_compact_obj(idf, avail_sched_obj_name, "On/Off", *sched_blocks)

    # assign the availability schedule using the supplied field paths
    for cls_name, obj_name, field_name in avail_field_paths:
        obj = aark.ep.obj.get_named(idf, cls_name, obj_name)
        obj[eppy.bunchhelpers.makefieldname(field_name)] = avail_sched_obj_name


def _set_thermostat(
    idf: IDF,
    zone_name: str,
    setpoint_cls_name: str,
    setpoint_obj_name: str,
    control_sched_obj_name: str,
) -> None:
    """Set the control mode and setpoint object for the zone thermostat."""
    # find the thermostat directly assigned to the zone
    (thermostat_obj,) = (
        obj
        for obj in idf.idfobjects["ZoneControl:Thermostat"]
        if zone_name == obj.Zone_or_ZoneList_Name
    )

    # replace the existing controls
    thermostat_obj.Control_Type_Schedule_Name = control_sched_obj_name
    thermostat_obj.Control_1_Object_Type = setpoint_cls_name
    thermostat_obj.Control_1_Name = setpoint_obj_name

    for i in range(2, 5):
        thermostat_obj[f"Control_{i}_Object_Type"] = ""
        thermostat_obj[f"Control_{i}_Name"] = ""

    aark.ep.obj.rstrip(thermostat_obj)


def _add_heating_setpoint(idf: IDF, zone_name: str, activity_name: str) -> None:
    """Add a heating setpoint to one zone."""
    setpoint_cls_name = "ThermostatSetpoint:SingleHeating"

    # get ncm data
    heating = ACTIVITY_DATABASE.get_heating(activity_name)

    # get object names
    control_sched_obj_name = aark.ncm._utils.sched_uid("heating_control")
    setpoint_sched_obj_name = aark.ncm._utils.prefix(heating["sched_name"])
    setpoint_obj_name = aark.ncm._utils.prefix(f"heating_setpoint_{activity_name}")

    # add schedule objects
    aark.ep.sched.add_constant_obj(idf, control_sched_obj_name, "Control", "1")
    _add_setpoint_scheds(idf, heating["sched_name"], heating["setpoint"])

    # add the heating setpoint object
    aark.ep.obj.add(
        idf,
        setpoint_cls_name,
        Name=setpoint_obj_name,
        Setpoint_Temperature_Schedule_Name=setpoint_sched_obj_name,
    )

    # update the existing zone thermostat
    _set_thermostat(
        idf, zone_name, setpoint_cls_name, setpoint_obj_name, control_sched_obj_name
    )


def _add_cooling_setpoint(idf: IDF, zone_name: str, activity_name: str) -> None:
    """Add a cooling setpoint to one zone."""
    setpoint_cls_name = "ThermostatSetpoint:SingleCooling"

    # get ncm data
    cooling = ACTIVITY_DATABASE.get_cooling(activity_name)

    # get object names
    control_sched_obj_name = aark.ncm._utils.sched_uid("cooling_control")
    setpoint_sched_obj_name = aark.ncm._utils.prefix(cooling["sched_name"])
    setpoint_obj_name = aark.ncm._utils.prefix(f"cooling_setpoint_{activity_name}")

    # add schedule objects
    aark.ep.sched.add_constant_obj(idf, control_sched_obj_name, "Control", "2")
    _add_setpoint_scheds(idf, cooling["sched_name"], cooling["setpoint"])

    # add the cooling setpoint object
    aark.ep.obj.add(
        idf,
        setpoint_cls_name,
        Name=setpoint_obj_name,
        Setpoint_Temperature_Schedule_Name=setpoint_sched_obj_name,
    )

    # update the existing zone thermostat
    _set_thermostat(
        idf, zone_name, setpoint_cls_name, setpoint_obj_name, control_sched_obj_name
    )


def _add_heating_cooling_setpoint(idf: IDF, zone_name: str, activity_name: str) -> None:
    """Add heating and cooling setpoints to one zone."""
    setpoint_cls_name = "ThermostatSetpoint:DualSetpoint"

    # get ncm data
    heating = ACTIVITY_DATABASE.get_heating(activity_name)
    cooling = ACTIVITY_DATABASE.get_cooling(activity_name)

    # get object names
    control_sched_obj_name = aark.ncm._utils.sched_uid("heating_cooling_control")
    heating_setpoint_sched_obj_name = aark.ncm._utils.prefix(heating["sched_name"])
    cooling_setpoint_sched_obj_name = aark.ncm._utils.prefix(cooling["sched_name"])
    setpoint_obj_name = aark.ncm._utils.prefix(
        f"heating_cooling_setpoint_{activity_name}"
    )

    # add schedule objects
    aark.ep.sched.add_constant_obj(idf, control_sched_obj_name, "Control", "4")
    _add_setpoint_scheds(idf, heating["sched_name"], heating["setpoint"])
    _add_setpoint_scheds(idf, cooling["sched_name"], cooling["setpoint"])

    # add the dual setpoint object
    aark.ep.obj.add(
        idf,
        setpoint_cls_name,
        Name=setpoint_obj_name,
        Heating_Setpoint_Temperature_Schedule_Name=heating_setpoint_sched_obj_name,
        Cooling_Setpoint_Temperature_Schedule_Name=cooling_setpoint_sched_obj_name,
    )

    # update the existing zone thermostat
    _set_thermostat(
        idf, zone_name, setpoint_cls_name, setpoint_obj_name, control_sched_obj_name
    )


def apply(
    idf: IDF,
    heating_zone_map: ActivityMap | None = None,
    cooling_zone_map: ActivityMap | None = None,
    heating_start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    heating_end_month_day: MonthDay = YEAR_END_MONTH_DAY,
    cooling_start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    cooling_end_month_day: MonthDay = YEAR_END_MONTH_DAY,
    heating_avail_field_paths: Sequence[tuple[str, str, str]] = (),
    cooling_avail_field_paths: Sequence[tuple[str, str, str]] = (),
) -> None:
    """Apply thermostats to the IDF.

    Load `aark.ncm.data.ACTIVITY_DATABASE` with `load(cur)` before calling.

    Parameters
    ----------
    idf : IDF
        IDF to receive thermostats.
    heating_zone_map, cooling_zone_map : ActivityMap or None, optional
        NCM activity names mapped to names of one or more `Zone` objects in `idf` to
        heat or cool. At least one map must be non-empty, and zones in both maps must
        have the same activity assignment. For example:

        ```python
        heating_zone_map = {
            "Dwell_DomBed": ["bedroom_1", "bedroom_2"],
            "Dwell_DomLounge": ["lounge"],
        }
        cooling_zone_map = {
            "Dwell_DomBed": ["bedroom_2", "bedroom_3"],
            "Dwell_DomLounge": ["lounge"],
        }
        ```

        Here, `bedroom_1` has heating only, `bedroom_3` has cooling only, and
        `bedroom_2` and `lounge` have both.
    heating_start_month_day, heating_end_month_day : MonthDay, optional
        Inclusive heating availability period as `(month, day)` pairs, defaulting to the
        full year. A start after the end spans New Year. For design and custom days, see
        'Notes'.
    cooling_start_month_day, cooling_end_month_day : MonthDay, optional
        Cooling availability period, with the same conventions as heating. For design
        and custom days, see 'Notes'.
    heating_avail_field_paths, cooling_avail_field_paths : Sequence[tuple[str, str, str]], optional
        Paths to heating and cooling availability fields in `idf`, given as
        `(class_name, object_name, field_name)` tuples. For example:

        ```python
        heating_avail_field_paths = [
            ("AvailabilityManager:Scheduled", "Heating Manager", "Schedule Name"),
        ]
        ```

    Notes
    -----
    Design and custom days use the following constant values, independently of
    the specified availability periods.

    | Profile              | Winter design day | Summer design day | Custom days    |
    | -------------------- | ----------------- | ----------------- | -------------- |
    | Heating setpoint     | Activity value    | Activity value    | Activity value |
    | Cooling setpoint     | Activity value    | Activity value    | Activity value |
    | Heating availability | On                | Off               | Off            |
    | Cooling availability | Off               | On                | Off            |
    """
    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)

    # normalise omitted zone maps
    # TODO: use frozendict as default when moving to py315
    if heating_zone_map is None:
        heating_zone_map = {}

    if cooling_zone_map is None:
        cooling_zone_map = {}

    # validate user inputs
    _validate_zone_maps(idf, heating_zone_map, cooling_zone_map)
    aark._utils.validate_month_days(
        heating_start_month_day,
        heating_end_month_day,
        cooling_start_month_day,
        cooling_end_month_day,
    )
    _validate_avail_field_paths(
        idf, heating_avail_field_paths, cooling_avail_field_paths
    )

    # apply heating and cooling to each activity's zones
    for activity_name in heating_zone_map.keys() | cooling_zone_map.keys():
        heating_zone_names = set(heating_zone_map.get(activity_name, ()))
        cooling_zone_names = set(cooling_zone_map.get(activity_name, ()))

        # add the heating setpoint
        for zone_name in sorted(heating_zone_names - cooling_zone_names):
            _add_heating_setpoint(idf, zone_name, activity_name)

        # add the cooling setpoint
        for zone_name in sorted(cooling_zone_names - heating_zone_names):
            _add_cooling_setpoint(idf, zone_name, activity_name)

        # add the heating and cooling setpoints
        for zone_name in sorted(heating_zone_names & cooling_zone_names):
            _add_heating_cooling_setpoint(idf, zone_name, activity_name)

    # add heating availability
    if heating_avail_field_paths:
        _add_avail(
            idf,
            aark.ncm._utils.sched_uid("heating_avail"),
            heating_avail_field_paths,
            heating_start_month_day,
            heating_end_month_day,
            "WinterDesignDay",
        )

    # add cooling availability
    if cooling_avail_field_paths:
        _add_avail(
            idf,
            aark.ncm._utils.sched_uid("cooling_avail"),
            cooling_avail_field_paths,
            cooling_start_month_day,
            cooling_end_month_day,
            "SummerDesignDay",
        )


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_zone_maps(
    idf: IDF, heating_zone_map: ActivityMap, cooling_zone_map: ActivityMap
) -> None:
    """Validate heating and cooling zone maps and their activity assignments."""
    # at least one zone map must be non-empty
    if (not heating_zone_map) and (not cooling_zone_map):
        raise ValueError(
            f"Empty heating and cooling zone maps: {(heating_zone_map, cooling_zone_map)}."
        )

    # each non-empty zone map must be valid
    for zone_map in (heating_zone_map, cooling_zone_map):
        if zone_map:
            aark.ncm._utils.validate_zone_map(idf, zone_map)

    # zones in both maps must have the same activity assignment
    heating_zone2activity_name = {
        zone_name: activity_name
        for activity_name, zone_names in heating_zone_map.items()
        for zone_name in zone_names
    }
    cooling_zone2activity_name = {
        zone_name: activity_name
        for activity_name, zone_names in cooling_zone_map.items()
        for zone_name in zone_names
    }

    for zone_name in (
        heating_zone2activity_name.keys() & cooling_zone2activity_name.keys()
    ):
        heating_activity_name = heating_zone2activity_name[zone_name]
        cooling_activity_name = cooling_zone2activity_name[zone_name]

        if heating_activity_name != cooling_activity_name:
            raise ValueError(
                f"Conflicting heating and cooling activity assignments: {(zone_name, heating_activity_name, cooling_activity_name)}."
            )


def _validate_avail_field_paths(
    idf: IDF,
    heating_avail_field_paths: Sequence[tuple[str, str, str]],
    cooling_avail_field_paths: Sequence[tuple[str, str, str]],
) -> None:
    """Validate that availability field paths exist and do not conflict."""
    # heating and cooling field paths must not identify the same field
    normalised_heating_field_paths = {
        tuple(map(str.upper, field_path)) for field_path in heating_avail_field_paths
    }
    normalised_cooling_field_paths = {
        tuple(map(str.upper, field_path)) for field_path in cooling_avail_field_paths
    }
    conflicting_field_paths = (
        normalised_heating_field_paths & normalised_cooling_field_paths
    )
    if conflicting_field_paths:
        raise ValueError(
            f"Overlapping heating and cooling availability field paths: {sorted(conflicting_field_paths)}."
        )

    for cls_name, obj_name, field_name in (
        *heating_avail_field_paths,
        *cooling_avail_field_paths,
    ):
        # field paths must identify existing objects
        obj = aark.ep.obj.get_named(idf, cls_name, obj_name)

        # fields must exist on the identified objects
        if eppy.bunchhelpers.makefieldname(field_name) not in obj.fieldnames:
            raise ValueError(
                f"Missing availability field: {(cls_name, obj_name, field_name)}."
            )
