"""TM59:2017 Section 3.3 window and door openings."""

from typing import TYPE_CHECKING

import aark.ep._pact
import aark.ep.afn
import aark.ep.field
import aark.ep.obj
import aark.ep.sched
import aark.tm59._utils
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.ep.field import MAX_EP_STR_FIELD_LEN
from aark.tm59.data import (
    AWAKE_END_HOUR,
    AWAKE_START_HOUR,
    HABITABLE_ROOM_TYPES,
    INTERNAL_GAIN_PROFILES,
    SLEEP_ROOM_TYPES,
    STUDIO_TYPE,
    WINDOW_OPENING_THRESHOLD,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.tm59._utils import RoomMap


def _get_avail_hourly_factors(room_type: str) -> tuple[str, ...]:
    """Get availability hourly factors by room type."""
    if room_type in SLEEP_ROOM_TYPES:
        return tuple(
            "1" if AWAKE_START_HOUR <= hour < AWAKE_END_HOUR else "0"
            for hour in range(24)
        )

    else:
        occupancy_hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(
            "occupancy", room_type
        )
        return tuple(
            "0" if factor == "0" else "1" for factor in occupancy_hourly_factors
        )


def _add_program_to_calling_manager(idf: IDF, program_obj_name: str) -> None:
    """Add a program to the model-level window program calling manager."""
    calling_manager_cls_name = "EnergyManagementSystem:ProgramCallingManager"
    calling_manager_obj_name = aark.tm59._utils.prefix("window_vent")
    calling_point = "BeginTimestepBeforePredictor"

    if aark.ep.obj.has_named(idf, calling_manager_cls_name, calling_manager_obj_name):
        calling_manager_obj = aark.ep.obj.get_named(
            idf, calling_manager_cls_name, calling_manager_obj_name
        )

        if calling_manager_obj.EnergyPlus_Model_Calling_Point != calling_point:
            raise ValueError(
                f"Program calling manager exists at a different calling point: {calling_manager_obj.EnergyPlus_Model_Calling_Point}."
            )

        aark.ep.obj.rstrip(calling_manager_obj)
        n_programs = len(calling_manager_obj.fieldvalues) - 3
        if not any(
            calling_manager_obj[f"Program_Name_{i}"] == program_obj_name
            for i in range(1, n_programs + 1)
        ):
            calling_manager_obj[f"Program_Name_{n_programs + 1}"] = program_obj_name
    else:
        aark.ep.obj.add(
            idf,
            calling_manager_cls_name,
            Name=calling_manager_obj_name,
            EnergyPlus_Model_Calling_Point=calling_point,
            Program_Name_1=program_obj_name,
        )


def _add_window(
    idf: IDF,
    afn_surface_obj: EpBunch,
    zone_name: str,
    room_type: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add control for the window."""
    window_name = afn_surface_obj.Surface_Name
    max_vent_factor = aark.ep.field.with_default(
        afn_surface_obj.WindowDoor_Opening_Factor_or_Crack_Factor,
        afn_surface_obj,
        "WindowDoor_Opening_Factor_or_Crack_Factor",
    )
    avail_sched_obj_name = aark.tm59._utils.prefix(f"window_avail_{room_type}")
    avail_sensor_obj_name = aark.tm59._utils.erl_uid("window_avail", room_type)
    Ta_sensor_obj_name = aark.tm59._utils.erl_uid("Ta", zone_name)
    actuator_obj_name = aark.tm59._utils.erl_uid("vent_factor", window_name)
    program_obj_name = aark.tm59._utils.erl_uid("vent", window_name)
    program_lines = (
        f"IF {avail_sensor_obj_name} > 0",
        f"IF {Ta_sensor_obj_name} > {WINDOW_OPENING_THRESHOLD}",
        f"SET {actuator_obj_name} = {max_vent_factor}",
        "ELSE",
        f"SET {actuator_obj_name} = 0",
        "ENDIF",
        "ELSE",
        f"SET {actuator_obj_name} = 0",
        "ENDIF",
    )

    for line in program_lines:
        if len(line) > MAX_EP_STR_FIELD_LEN:
            raise ValueError(
                f"EMS program line exceeds {MAX_EP_STR_FIELD_LEN} characters: {line}."
            )

    # add the availability schedule
    avail_hourly_factors = _get_avail_hourly_factors(room_type)
    avail_sched_blocks = aark.ep.sched.make_compact_blocks(
        avail_hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(
        idf, avail_sched_obj_name, "On/Off", *avail_sched_blocks
    )

    # modify the afn surface object
    afn_surface_obj.Ventilation_Control_Mode = "Constant"
    afn_surface_obj.Venting_Availability_Schedule_Name = avail_sched_obj_name

    # add the availability sensor
    aark.ep.obj.add(
        idf,
        "EnergyManagementSystem:Sensor",
        Name=avail_sensor_obj_name,
        OutputVariable_or_OutputMeter_Index_Key_Name=avail_sched_obj_name,
        OutputVariable_or_OutputMeter_Name="Schedule Value",
    )

    # add the indoor air temperature sensor
    aark.ep.obj.add(
        idf,
        "EnergyManagementSystem:Sensor",
        Name=Ta_sensor_obj_name,
        OutputVariable_or_OutputMeter_Index_Key_Name=zone_name,
        OutputVariable_or_OutputMeter_Name="Zone Mean Air Temperature",
    )

    # add the actuator
    aark.ep.obj.add(
        idf,
        "EnergyManagementSystem:Actuator",
        Name=actuator_obj_name,
        Actuated_Component_Unique_Name=window_name,
        Actuated_Component_Type="AirFlow Network Window/Door Opening",
        Actuated_Component_Control_Type="Venting Opening Factor",
    )

    # add the program
    aark.ep.obj.add(
        idf,
        "EnergyManagementSystem:Program",
        Name=program_obj_name,
        **{f"Program_Line_{i}": line for i, line in enumerate(program_lines, start=1)},
    )

    # add the program to the calling manager
    _add_program_to_calling_manager(idf, program_obj_name)


def _apply_external_windows(
    idf: IDF, window_map: RoomMap, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the external window openings.

    External windows refer to external glazed openings, including windows and
    patio doors, in habitable rooms.
    """
    for room_type, window_names in window_map.items():
        for window_name in window_names:
            window_obj = aark.ep.obj.get_named(
                idf, "FenestrationSurface:Detailed", window_name
            )
            zone_name = aark.ep.obj.get_zone(window_obj).Name

            afn_surface_obj = aark.ep.afn.get_surface_obj(idf, window_name)

            _add_window(
                idf,
                afn_surface_obj,
                zone_name,
                room_type,
                start_month_day,
                end_month_day,
            )


def _apply_internal_doors(
    idf: IDF,
    door_names: Sequence[str],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Apply the internal door openings.

    Internal doors refer to intra-dwelling doors.
    """
    # add the availability schedule
    avail_hourly_factors = _get_avail_hourly_factors(STUDIO_TYPE)
    sched_obj_name = aark.tm59._utils.prefix("internal_door_avail")
    sched_blocks = aark.ep.sched.make_compact_blocks(
        avail_hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "On/Off", *sched_blocks)

    for door_name in door_names:
        afn_surface_obj = aark.ep.afn.get_surface_obj(idf, door_name)

        # modify the afn surface object
        afn_surface_obj.Ventilation_Control_Mode = "Constant"
        afn_surface_obj.Venting_Availability_Schedule_Name = sched_obj_name


def apply(
    idf: IDF,
    window_map: RoomMap,
    doors: Sequence[str],
    start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    end_month_day: MonthDay = YEAR_END_MONTH_DAY,
) -> None:
    """Apply the window and door openings to the IDF.

    `aark` requirements
    -------------------
    EnergyPlus version is 24.1 or later, with no `Space` object.

    Notes
    -----
    A key user input is `window_map` with the conceptual type:

    ```python
    dict[str, list[str]]
    ```

    Each key is a TM59 habitable room type, and each value is a list of external
    window names. `window_map` covers the whole model and is not grouped by dwelling.
    An example of `window_map` is:

    ```python
    window_map = {
        "living_kitchen": [
            "flat_1_living_kitchen_window",
            "flat_2_living_kitchen_patio_door",
        ],
        "double_bedroom": [
            "flat_1_bedroom_window",
        ],
    }
    ```

    Another key user input is `doors` with the conceptual type:

    ```python
    list[str]
    ```

    It is a list of internal door names. An example of `doors` is:

    ```python
    doors = [
        "flat_1_living-kitchen_door",
        "flat_2_bedroom-kitchen_door",
    ]
    ```
    """
    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)
    aark.ep._pact.validate_no_space(idf)

    # validate user inputs
    _validate_window_map(idf, window_map)
    _validate_doors(idf, doors)

    _apply_external_windows(idf, window_map, start_month_day, end_month_day)
    _apply_internal_doors(idf, doors, start_month_day, end_month_day)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_afn_opening(idf: IDF, fenestration_name: str) -> None:
    """Validate the AirflowNetwork objects for a fenestration."""
    # a fenestration must have one afn surface object
    afn_surface_obj = aark.ep.afn.get_surface_obj(idf, fenestration_name)

    # the afn surface must reference an opening component object
    if not any(
        aark.ep.obj.has_named(idf, cls_name, afn_surface_obj.Leakage_Component_Name)
        for cls_name in (
            "AirflowNetwork:MultiZone:Component:DetailedOpening",
            "AirflowNetwork:MultiZone:Component:SimpleOpening",
        )
    ):
        raise ValueError(
            f"Fenestration has no AirflowNetwork opening component: {fenestration_name}."
        )


def _validate_erl_uids(*src_names: str) -> None:
    """Validate that unique source names produce unique ERL UIDs."""
    # NOTE: even when object names in room maps exactly match a valid idf, removing
    #       unsupported characters can leave distinct names differing only by case:
    #       `Window-A` and `windowa` become `WindowA` and `windowa`. erl identifiers are
    #       case insensitive, so uids must be converted to uppercase before comparison.

    unique_src_names = set(src_names)

    # source names must produce valid erl uids
    unique_erl_uids = {
        aark.tm59._utils.erl_uid("7", src_name).upper() for src_name in unique_src_names
    }

    # erl uids must be unique case-insensitively
    if len(unique_src_names) != len(unique_erl_uids):
        raise ValueError(
            f"Source names produce duplicate ERL UIDs: {unique_src_names}."
        )


def _validate_window_map(idf: IDF, window_map: RoomMap) -> None:
    """Validate one window map."""
    # the window map must have a valid structure
    aark.tm59._utils.validate_room_map(window_map)

    # room types must be valid for window opening
    invalid_room_types = set(window_map) - HABITABLE_ROOM_TYPES
    if invalid_room_types:
        raise ValueError(
            f"Invalid room types for window opening: {invalid_room_types}."
        )

    window_names = [name for names in window_map.values() for name in names]

    # mapped window names must be unique and identify objects in the idf
    aark.ep.obj.validate_obj_names(idf, "FenestrationSurface:Detailed", *window_names)

    zone_names = []

    # NOTE: fast fail
    for window_name in window_names:
        # each window's parent surface and zone must exist exactly once
        window_obj = aark.ep.obj.get_named(
            idf, "FenestrationSurface:Detailed", window_name
        )
        zone_names.append(aark.ep.obj.get_zone(window_obj).Name)

        # each window must have afn surface and opening component objects
        _validate_afn_opening(idf, window_name)

    # zone names must produce valid erl uids without collisions
    _validate_erl_uids(*zone_names)

    # window names must produce valid erl uids without collisions
    _validate_erl_uids(*window_names)

    # room types must produce valid erl uids without collisions
    _validate_erl_uids(*window_map)


def _validate_doors(idf: IDF, door_names: Sequence[str]) -> None:
    """Validate a sequence of doors for applying internal door opening."""
    # the door sequence must not be empty
    if not door_names:
        raise ValueError(f"Empty doors: {door_names}.")

    # doors must be provided as a non-string sequence
    if isinstance(door_names, str):
        raise TypeError(f"Invalid door sequence: {door_names}.")

    # NOTE: fast fail
    for door_name in door_names:
        # the door must exist in the idf
        aark.ep.obj.get_named(idf, "FenestrationSurface:Detailed", door_name)

        # each door must have afn surface and opening component objects
        _validate_afn_opening(idf, door_name)
