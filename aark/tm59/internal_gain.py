"""TM59:2017 Section 5 internal gain profiles."""

from typing import TYPE_CHECKING

import aark.ep._pact
import aark.ep.obj
import aark.ep.sched
import aark.tm59._utils
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.tm59.data import (
    ANCILLARY_ROOM_TYPES,
    BEDROOM_TYPES,
    COMMUNAL_CORRIDOR_TYPE,
    HABITABLE_ROOM_TYPES,
    INTERNAL_GAIN_PROFILES,
    STUDIO_TYPE,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.tm59._utils import RoomMap


def _add_occupancy(
    idf: IDF,
    zone_name: str,
    room_type: str,
    n_bedrooms: int,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add occupancy gain to the zone."""
    gain_type = "occupancy"

    # get tm59 data
    n_people = INTERNAL_GAIN_PROFILES.get_n_people(room_type, n_bedrooms)
    metabolic_rate = INTERNAL_GAIN_PROFILES.get_peak_load(gain_type, room_type)
    sensible_frac = INTERNAL_GAIN_PROFILES.get_sensible_frac(room_type)
    occupancy_hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(
        gain_type, room_type
    )
    metabolic_hourly_factors = (metabolic_rate,) * 24

    # get object names
    occupancy_sched_obj_name = aark.tm59._utils.sched_uid(gain_type, room_type)
    metabolic_sched_obj_name = aark.tm59._utils.sched_uid("metabolic")
    gain_obj_name = aark.tm59._utils.gain_uid(gain_type, zone_name)

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
    aark.ep.obj.add(
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


def _add_equipment(
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
    sched_obj_name = aark.tm59._utils.sched_uid(gain_type, room_type)
    gain_obj_name = aark.tm59._utils.gain_uid(gain_type, zone_name)

    # add schedule objects
    sched_blocks = aark.ep.sched.make_compact_blocks(
        hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "Fraction", *sched_blocks)

    # add gain objects
    aark.ep.obj.add(
        idf,
        "ElectricEquipment",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Schedule_Name=sched_obj_name,
        Design_Level_Calculation_Method="EquipmentLevel",
        Design_Level=peak_load,
    )


def _add_lighting(
    idf: IDF, zone_name: str, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Add lighting gain to the zone."""
    gain_type = "lighting"

    # get tm59 data
    peak_load = INTERNAL_GAIN_PROFILES.get_peak_load(gain_type)
    hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(gain_type)

    # get object names
    sched_obj_name = aark.tm59._utils.sched_uid(gain_type)
    gain_obj_name = aark.tm59._utils.gain_uid(gain_type, zone_name)

    # add schedule objects
    sched_blocks = aark.ep.sched.make_compact_blocks(
        hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "Fraction", *sched_blocks)

    # add gain objects
    aark.ep.obj.add(
        idf,
        "Lights",
        Name=gain_obj_name,
        Zone_or_ZoneList_or_Space_or_SpaceList_Name=zone_name,
        Schedule_Name=sched_obj_name,
        Design_Level_Calculation_Method="Watts/Area",
        Watts_per_Floor_Area=peak_load,
    )


def _apply_dwelling(
    idf: IDF, zone_map: RoomMap, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the internal gain profiles to a dwelling."""
    n_bedrooms = sum(len(zone_map.get(room_type, ())) for room_type in BEDROOM_TYPES)

    for room_type, zone_names in zone_map.items():
        for zone_name in zone_names:
            _add_lighting(idf, zone_name, start_month_day, end_month_day)

            if room_type in HABITABLE_ROOM_TYPES:
                _add_occupancy(
                    idf,
                    zone_name,
                    room_type,
                    n_bedrooms,
                    start_month_day,
                    end_month_day,
                )
                _add_equipment(
                    idf, zone_name, room_type, start_month_day, end_month_day
                )


def _apply_communal_corridors(
    idf: IDF, zone_map: RoomMap, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the internal gain profiles to communal corridors."""
    for zone_name in zone_map[COMMUNAL_CORRIDOR_TYPE]:
        _add_lighting(idf, zone_name, start_month_day, end_month_day)


def apply(
    idf: IDF,
    zone_maps: Sequence[RoomMap],
    start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    end_month_day: MonthDay = YEAR_END_MONTH_DAY,
) -> None:
    """Apply the internal gain profiles to the IDF.

    `aark` requirements
    -------------------
    EnergyPlus version is 24.1 or later, with no `Space` object.

    Notes
    -----
    A key user input is `zone_maps` with the conceptual type:

    ```python
    list[dict[str, list[str]]]
    ```

    Each item is a single `zone_map` representing either a dwelling or a collection
    of communal corridors. Each `zone_map` key is a TM59 room type, and each value is
    a list of zone names. An example of `zone_maps` is:

    ```python
    zone_maps = [
        {
            "living_kitchen": ["flat_1_living_kitchen"],
            "double_bedroom": ["flat_1_bedroom_1", "flat_1_bedroom_2"],
            "single_bedroom": ["flat_1_bedroom_3"],
            "bathroom": ["flat_1_bathroom"],
            "hall": ["flat_1_hall"],
        },
        {
            "living": ["flat_2_living"],
            "kitchen": ["flat_2_kitchen"],
            "double_bedroom": ["flat_2_bedroom"],
            "bathroom": ["flat_2_bathroom"],
            "hall": ["flat_2_hall"],
        },
        {
            "communal_corridor": [
                "corridor_floor_1",
                "corridor_floor_2",
                "corridor_floor_3",
            ]
        },
    ]
    ```
    """
    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)
    aark.ep._pact.validate_no_space(idf)

    # validate user inputs
    _validate_zone_maps(idf, zone_maps)

    # apply to each dwelling or communal corridor
    for zone_map in zone_maps:
        if _is_communal_corridor_zone_map(zone_map):
            _apply_communal_corridors(idf, zone_map, start_month_day, end_month_day)
        else:
            _apply_dwelling(idf, zone_map, start_month_day, end_month_day)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_zone_map(zone_map: RoomMap) -> None:
    """Validate one room-to-zone map."""
    # the zone map must have a valid structure
    aark.tm59._utils.validate_room_map(zone_map)

    room_types = set(zone_map)

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
        # a dwelling must contain at least one bedroom
        n_bedrooms = sum(
            len(zone_map.get(room_type, ())) for room_type in BEDROOM_TYPES
        )

        if n_bedrooms == 0:
            raise ValueError(f"Missing bedrooms: {zone_map}.")


def _validate_zone_maps(idf: IDF, zone_maps: Sequence[RoomMap]) -> None:
    """Validate all room-to-zone maps."""
    # the map sequence must not be empty
    if not zone_maps:
        raise ValueError(f"Empty zone maps: {zone_maps}.")

    # each zone map must have a valid structure
    for zone_map in zone_maps:
        _validate_zone_map(zone_map)

    # mapped zone names must be unique and exist in the idf
    aark.tm59._utils.validate_mapped_obj_names(idf, "Zone", *zone_maps)


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def _is_communal_corridor_zone_map(zone_map: RoomMap) -> bool:
    """Return whether a zone map represents communal corridors."""
    return set(zone_map) == {COMMUNAL_CORRIDOR_TYPE}
