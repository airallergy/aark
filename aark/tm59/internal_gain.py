"""TM59:2017 Section 5 internal gain profiles."""

from typing import TYPE_CHECKING

import aark.ep.generic
import aark.ep.sched
import aark.tm59.utils
import aark.validation.ep
from aark.tm59.data import (
    BEDROOM_TYPES,
    COMMUNAL_CORRIDOR_TYPE,
    HABITABLE_ROOM_TYPES,
    INTERNAL_GAIN_PROFILES,
    N_BEDROOMS_DEPENDENT_ROOM_TYPES,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.modeleditor import IDF

    from aark.ep.sched import MonthDay
    from aark.tm59.utils import ZoneMap


def add_occupancy(
    idf: IDF,
    zone_name: str,
    room_type: str,
    n_bedrooms: int,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add occupancy gain to the zone."""
    gain_type = "occupancy"

    if room_type not in N_BEDROOMS_DEPENDENT_ROOM_TYPES:
        n_bedrooms = -1

    # get tm59 data
    n_people = INTERNAL_GAIN_PROFILES.get_n_people(room_type, n_bedrooms)
    metabolic_rate = INTERNAL_GAIN_PROFILES.get_peak_load(
        gain_type, room_type, n_bedrooms
    )
    sensible_frac = INTERNAL_GAIN_PROFILES.get_sensible_frac(room_type, n_bedrooms)
    occupancy_hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(
        gain_type, room_type, n_bedrooms
    )
    metabolic_hourly_factors = (metabolic_rate,) * 24

    # get object names
    occupancy_sched_obj_name = aark.tm59.utils.sched_uid(gain_type, room_type)
    metabolic_sched_obj_name = aark.tm59.utils.sched_uid("metabolic")
    gain_obj_name = aark.tm59.utils.gain_uid(gain_type, zone_name)

    # add schedule objects
    occupancy_sched_blocks = aark.ep.sched.make_compact_blocks(
        occupancy_hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(
        idf, occupancy_sched_obj_name, "Fraction", *occupancy_sched_blocks
    )

    metabolic_sched_blocks = aark.ep.sched.make_compact_blocks(metabolic_hourly_factors)
    aark.ep.sched.add_compact_obj(
        idf, metabolic_sched_obj_name, "Metabolism", *metabolic_sched_blocks
    )

    # add gain objects
    aark.ep.generic.add_obj(
        idf,
        "People",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Number_of_People_Schedule_Name=occupancy_sched_obj_name,
        Number_of_People_Calculation_Method="People",
        Number_of_People=n_people,
        Sensible_Heat_Fraction=sensible_frac,
        Activity_Level_Schedule_Name=metabolic_sched_obj_name,
    )


def add_equipment(
    idf: IDF,
    zone_name: str,
    room_type: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add equipment gain to the zone."""
    gain_type = "equipment"

    # get tm59 data
    peak_load = INTERNAL_GAIN_PROFILES.get_peak_load(gain_type, room_type)
    hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(gain_type, room_type)

    # get object names
    sched_obj_name = aark.tm59.utils.sched_uid(gain_type, room_type)
    gain_obj_name = aark.tm59.utils.gain_uid(gain_type, zone_name)

    # add schedule objects
    sched_blocks = aark.ep.sched.make_compact_blocks(
        hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "Fraction", *sched_blocks)

    # add gain objects
    aark.ep.generic.add_obj(
        idf,
        "ElectricEquipment",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Schedule_Name=sched_obj_name,
        Design_Level_Calculation_Method="EquipmentLevel",
        Design_Level=peak_load,
    )


def add_lighting(
    idf: IDF, zone_name: str, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Add lighting gain to the zone."""
    gain_type = "lighting"

    # get tm59 data
    peak_load = INTERNAL_GAIN_PROFILES.get_peak_load(gain_type)
    hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(gain_type)

    # get object names
    sched_obj_name = aark.tm59.utils.sched_uid(gain_type)
    gain_obj_name = aark.tm59.utils.gain_uid(gain_type, zone_name)

    # add schedule objects
    sched_blocks = aark.ep.sched.make_compact_blocks(
        hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "Fraction", *sched_blocks)

    # add gain objects
    aark.ep.generic.add_obj(
        idf,
        "Lights",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Schedule_Name=sched_obj_name,
        Design_Level_Calculation_Method="Watts/Area",
        Watts_per_Floor_Area=peak_load,
    )


def apply_dwelling(
    idf: IDF, zone_map: ZoneMap, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the internal gain profiles to a dwelling."""
    n_bedrooms = sum(len(zone_map.get(room_type, ())) for room_type in BEDROOM_TYPES)

    for room_type, zone_names in zone_map.items():
        for zone_name in zone_names:
            add_lighting(idf, zone_name, start_month_day, end_month_day)

            if room_type in HABITABLE_ROOM_TYPES:
                add_occupancy(
                    idf,
                    zone_name,
                    room_type,
                    n_bedrooms,
                    start_month_day,
                    end_month_day,
                )
                add_equipment(idf, zone_name, room_type, start_month_day, end_month_day)


def apply_communal_corridors(
    idf: IDF, zone_map: ZoneMap, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the internal gain profiles to communal corridors."""
    for zone_name in zone_map[COMMUNAL_CORRIDOR_TYPE]:
        add_lighting(idf, zone_name, start_month_day, end_month_day)


def apply(
    idf: IDF,
    zone_maps: Sequence[ZoneMap],
    start_month_day: MonthDay = (1, 1),
    end_month_day: MonthDay = (12, 31),
) -> None:
    """Apply the internal gain profiles to the idf.

    `aark` assumptions
    ------------------
    EnergyPlus version is 24.1 or later, with no `Space` object.
    """
    # validate aark assumptions
    aark.validation.ep.validate_ep_ver(idf)
    aark.validation.ep.validate_no_space(idf)

    # validate user inputs
    aark.tm59.utils.validate_zone_maps(idf, zone_maps)

    # apply to each dwelling or communal corridor
    for zone_map in zone_maps:
        if aark.tm59.utils.is_communal_corridor_zone_map(zone_map):
            apply_communal_corridors(idf, zone_map, start_month_day, end_month_day)
        else:
            apply_dwelling(idf, zone_map, start_month_day, end_month_day)
