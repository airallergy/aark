"""NCM heating and cooling profiles."""

from typing import TYPE_CHECKING

import aark._utils
import aark.ep._pact
import aark.ep.obj
import aark.ep.sched
import aark.ncm._utils
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.ncm.data import ACTIVITY_DATABASE

if TYPE_CHECKING:
    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.ncm._utils import ActivityMap


def _add_setpoint_scheds(idf: IDF, setpoint_sched_name: str) -> None:
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
    )


def _add_avail_sched(
    idf: IDF,
    avail_sched_obj_name: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add a seasonal availability schedule."""
    # mask availability values outside the active period
    sched_endpoints = aark.ncm._utils.mask_endpoints(
        [(YEAR_END_MONTH_DAY, "1")], "0", start_month_day, end_month_day
    )

    # build the compact availability schedule
    sched_blocks = []
    for month_day, val in sched_endpoints:
        sched_blocks.append(aark.ep.sched.make_compact_block(month_day, (val,) * 24))

    # add the availability schedule object
    aark.ep.sched.add_compact_obj(idf, avail_sched_obj_name, "On/Off", *sched_blocks)


def _add_zone_objs(
    idf: IDF,
    zone_name: str,
    setpoint_cls_name: str,
    setpoint_obj_name: str,
    control_sched_obj_name: str,
    heating_avail_sched_obj_name: str,
    cooling_avail_sched_obj_name: str,
) -> None:
    """Add one zone's thermostat, ideal loads system and equipment connections."""
    # get object and node names
    thermostat_obj_name = aark.ncm._utils.prefix(f"thermostat_{zone_name}")
    sys_obj_name = aark.ncm._utils.prefix(f"ideal_loads_{zone_name}")
    equipment_list_obj_name = aark.ncm._utils.prefix(f"equipment_list_{zone_name}")
    supply_air_node_name = aark.ncm._utils.prefix(f"supply_{zone_name}")
    zone_air_node_name = aark.ncm._utils.prefix(f"air_{zone_name}")
    return_air_node_name = aark.ncm._utils.prefix(f"return_{zone_name}")

    # add the zone thermostat object
    aark.ep.obj.add(
        idf,
        "ZoneControl:Thermostat",
        Name=thermostat_obj_name,
        Zone_or_ZoneList_Name=zone_name,
        Control_Type_Schedule_Name=control_sched_obj_name,
        Control_1_Object_Type=setpoint_cls_name,
        Control_1_Name=setpoint_obj_name,
    )

    # add the ideal loads system object
    aark.ep.obj.add(
        idf,
        "ZoneHVAC:IdealLoadsAirSystem",
        Name=sys_obj_name,
        Zone_Supply_Air_Node_Name=supply_air_node_name,
        Heating_Availability_Schedule_Name=heating_avail_sched_obj_name,
        Cooling_Availability_Schedule_Name=cooling_avail_sched_obj_name,
    )

    # add the zone equipment list object
    aark.ep.obj.add(
        idf,
        "ZoneHVAC:EquipmentList",
        Name=equipment_list_obj_name,
        Zone_Equipment_1_Object_Type="ZoneHVAC:IdealLoadsAirSystem",
        Zone_Equipment_1_Name=sys_obj_name,
        Zone_Equipment_1_Cooling_Sequence="1",
        Zone_Equipment_1_Heating_or_NoLoad_Sequence="1",
    )

    # add the zone equipment connections object
    aark.ep.obj.add(
        idf,
        "ZoneHVAC:EquipmentConnections",
        Zone_Name=zone_name,
        Zone_Conditioning_Equipment_List_Name=equipment_list_obj_name,
        Zone_Air_Inlet_Node_or_NodeList_Name=supply_air_node_name,
        Zone_Air_Node_Name=zone_air_node_name,
        Zone_Return_Air_Node_or_NodeList_Name=return_air_node_name,
    )


def _add_heating(
    idf: IDF,
    zone_name: str,
    activity_name: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add ideal loads heating to one zone."""
    setpoint_cls_name = "ThermostatSetpoint:SingleHeating"

    # get ncm data
    heating = ACTIVITY_DATABASE.get_heating(activity_name)

    # get object names
    control_sched_obj_name = aark.ncm._utils.sched_uid("heating_control")
    setpoint_sched_obj_name = aark.ncm._utils.prefix(heating["sched_name"])
    avail_sched_obj_name = aark.ncm._utils.sched_uid("heating_avail")
    setpoint_obj_name = aark.ncm._utils.prefix(f"heating_setpoint_{activity_name}")

    # add schedule objects
    aark.ep.sched.add_constant_obj(idf, control_sched_obj_name, "Control", "1")
    _add_setpoint_scheds(idf, heating["sched_name"])
    _add_avail_sched(idf, avail_sched_obj_name, start_month_day, end_month_day)

    # add the heating setpoint object
    aark.ep.obj.add(
        idf,
        setpoint_cls_name,
        Name=setpoint_obj_name,
        Setpoint_Temperature_Schedule_Name=setpoint_sched_obj_name,
    )

    # add the zone thermostat, system and equipment connections
    _add_zone_objs(
        idf,
        zone_name,
        setpoint_cls_name,
        setpoint_obj_name,
        control_sched_obj_name,
        avail_sched_obj_name,
        "",
    )


def _add_cooling(
    idf: IDF,
    zone_name: str,
    activity_name: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add ideal loads cooling to one zone."""
    setpoint_cls_name = "ThermostatSetpoint:SingleCooling"

    # get ncm data
    cooling = ACTIVITY_DATABASE.get_cooling(activity_name)

    # get object names
    control_sched_obj_name = aark.ncm._utils.sched_uid("cooling_control")
    setpoint_sched_obj_name = aark.ncm._utils.prefix(cooling["sched_name"])
    avail_sched_obj_name = aark.ncm._utils.sched_uid("cooling_avail")
    setpoint_obj_name = aark.ncm._utils.prefix(f"cooling_setpoint_{activity_name}")

    # add schedule objects
    aark.ep.sched.add_constant_obj(idf, control_sched_obj_name, "Control", "2")
    _add_setpoint_scheds(idf, cooling["sched_name"])
    _add_avail_sched(idf, avail_sched_obj_name, start_month_day, end_month_day)

    # add the cooling setpoint object
    aark.ep.obj.add(
        idf,
        setpoint_cls_name,
        Name=setpoint_obj_name,
        Setpoint_Temperature_Schedule_Name=setpoint_sched_obj_name,
    )

    # add the zone thermostat, system and equipment connections
    _add_zone_objs(
        idf,
        zone_name,
        setpoint_cls_name,
        setpoint_obj_name,
        control_sched_obj_name,
        "",
        avail_sched_obj_name,
    )


def _add_heating_cooling(
    idf: IDF,
    zone_name: str,
    activity_name: str,
    heating_start_month_day: MonthDay,
    heating_end_month_day: MonthDay,
    cooling_start_month_day: MonthDay,
    cooling_end_month_day: MonthDay,
) -> None:
    """Add ideal loads heating and cooling to one zone."""
    setpoint_cls_name = "ThermostatSetpoint:DualSetpoint"

    # get ncm data
    heating = ACTIVITY_DATABASE.get_heating(activity_name)
    cooling = ACTIVITY_DATABASE.get_cooling(activity_name)

    # get object names
    control_sched_obj_name = aark.ncm._utils.sched_uid("heating_cooling_control")
    heating_setpoint_sched_obj_name = aark.ncm._utils.prefix(heating["sched_name"])
    cooling_setpoint_sched_obj_name = aark.ncm._utils.prefix(cooling["sched_name"])
    heating_avail_sched_obj_name = aark.ncm._utils.sched_uid("heating_avail")
    cooling_avail_sched_obj_name = aark.ncm._utils.sched_uid("cooling_avail")
    setpoint_obj_name = aark.ncm._utils.prefix(
        f"heating_cooling_setpoint_{activity_name}"
    )

    # add schedule objects
    aark.ep.sched.add_constant_obj(idf, control_sched_obj_name, "Control", "4")
    _add_setpoint_scheds(idf, heating["sched_name"])
    _add_setpoint_scheds(idf, cooling["sched_name"])
    _add_avail_sched(
        idf,
        heating_avail_sched_obj_name,
        heating_start_month_day,
        heating_end_month_day,
    )
    _add_avail_sched(
        idf,
        cooling_avail_sched_obj_name,
        cooling_start_month_day,
        cooling_end_month_day,
    )

    # add the dual setpoint object
    aark.ep.obj.add(
        idf,
        setpoint_cls_name,
        Name=setpoint_obj_name,
        Heating_Setpoint_Temperature_Schedule_Name=heating_setpoint_sched_obj_name,
        Cooling_Setpoint_Temperature_Schedule_Name=cooling_setpoint_sched_obj_name,
    )

    # add the zone thermostat, system and equipment connections
    _add_zone_objs(
        idf,
        zone_name,
        setpoint_cls_name,
        setpoint_obj_name,
        control_sched_obj_name,
        heating_avail_sched_obj_name,
        cooling_avail_sched_obj_name,
    )


def apply(
    idf: IDF,
    heating_zone_map: ActivityMap | None = None,
    cooling_zone_map: ActivityMap | None = None,
    heating_start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    heating_end_month_day: MonthDay = YEAR_END_MONTH_DAY,
    cooling_start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    cooling_end_month_day: MonthDay = YEAR_END_MONTH_DAY,
) -> None:
    """Apply thermostats to the IDF.

    Load `aark.ncm.data.ACTIVITY_DATABASE` with `load(cur)` before calling.

    Parameters
    ----------
    idf : IDF
        IDF to receive thermostats.
    heating_zone_map, cooling_zone_map : ActivityMap or None, optional
        Activity names mapped to one or more zones to heat or cool. At least
        one map must be non-empty, and zones in both maps must have the same
        activity assignment. For example:

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
        Inclusive heating availability period as `(month, day)` pairs, defaulting
        to the whole year. A start after the end spans New Year.
    cooling_start_month_day, cooling_end_month_day : MonthDay, optional
        Cooling availability period, with the same conventions as heating.
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

    # apply heating and cooling to each activity's zones
    for activity_name in heating_zone_map.keys() | cooling_zone_map.keys():
        heating_zone_names = set(heating_zone_map.get(activity_name, ()))
        cooling_zone_names = set(cooling_zone_map.get(activity_name, ()))

        # add heating only
        for zone_name in sorted(heating_zone_names - cooling_zone_names):
            _add_heating(
                idf,
                zone_name,
                activity_name,
                heating_start_month_day,
                heating_end_month_day,
            )

        # add cooling only
        for zone_name in sorted(cooling_zone_names - heating_zone_names):
            _add_cooling(
                idf,
                zone_name,
                activity_name,
                cooling_start_month_day,
                cooling_end_month_day,
            )

        # add heating and cooling
        for zone_name in sorted(heating_zone_names & cooling_zone_names):
            _add_heating_cooling(
                idf,
                zone_name,
                activity_name,
                heating_start_month_day,
                heating_end_month_day,
                cooling_start_month_day,
                cooling_end_month_day,
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
