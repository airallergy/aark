"""TM59:2017 Section 3.3 window and door openings."""
# ruff: noqa: N806

from typing import TYPE_CHECKING

import aark.ep.afn
import aark.ep.generic
import aark.ep.sched
import aark.tm59
import aark.tm59.utils
import aark.validation.ep
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

    from aark import MonthDay
    from aark.tm59.utils import RoomMap


def get_avail_hourly_factors(room_type: str) -> tuple[str, ...]:
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


def add_program_to_calling_manager(idf: IDF, program_obj_name: str) -> None:
    """Add a program to the model-level window program calling manager."""
    calling_manager_cls_name = "EnergyManagementSystem:ProgramCallingManager"
    calling_manager_obj_name = aark.tm59.prefix("window_opening")
    calling_point = "BeginTimestepBeforePredictor"

    if aark.ep.generic.has_named_obj(
        idf, calling_manager_cls_name, calling_manager_obj_name
    ):
        calling_manager_obj = aark.ep.generic.get_named_object(
            idf, calling_manager_cls_name, calling_manager_obj_name
        )

        if calling_manager_obj.EnergyPlus_Model_Calling_Point != calling_point:
            raise ValueError(
                f"Program calling manager exists at a different calling point: {calling_manager_obj.EnergyPlus_Model_Calling_Point}."
            )

        aark.ep.generic.rstrip_obj(calling_manager_obj)
        n_programs = len(calling_manager_obj.fieldvalues) - 3
        if not any(
            calling_manager_obj[f"Program_Name_{i}"] == program_obj_name
            for i in range(1, n_programs + 1)
        ):
            calling_manager_obj[f"Program_Name_{n_programs + 1}"] = program_obj_name
    else:
        aark.ep.generic.add_obj(
            idf,
            calling_manager_cls_name,
            Name=calling_manager_obj_name,
            EnergyPlus_Model_Calling_Point=calling_point,
            Program_Name_1=program_obj_name,
        )


def add_window(
    idf: IDF,
    afn_surface_obj: EpBunch,
    zone_name: str,
    room_type: str,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add control for the window."""
    window_obj_name = afn_surface_obj.Surface_Name
    avail_sched_obj_name = aark.tm59.prefix(f"window_avail_{room_type}")
    avail_sensor_obj_name = aark.tm59.utils.erl_uid("window_avail", room_type)
    Ta_sensor_obj_name = aark.tm59.utils.erl_uid("Ta", zone_name)
    actuator_obj_name = aark.tm59.utils.erl_uid("opening_factor", window_obj_name)
    program_obj_name = aark.tm59.utils.erl_uid("opening", window_obj_name)
    program_lines = (
        f"IF {avail_sensor_obj_name} > 0",
        f"IF {Ta_sensor_obj_name} > {WINDOW_OPENING_THRESHOLD}",
        f"SET {actuator_obj_name} = 1",
        "ELSE",
        f"SET {actuator_obj_name} = 0",
        "ENDIF",
        "ELSE",
        f"SET {actuator_obj_name} = 0",
        "ENDIF",
    )

    for line in program_lines:
        if len(line) > aark.ep.generic.MAX_EP_STR_FIELD_LEN:
            raise ValueError(
                f"EMS program line exceeds {aark.ep.generic.MAX_EP_STR_FIELD_LEN} characters: {line}."
            )

    # add the availability schedule
    avail_hourly_factors = get_avail_hourly_factors(room_type)
    avail_sched_blocks = aark.ep.sched.make_compact_blocks(
        avail_hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(
        idf, avail_sched_obj_name, "On/Off", *avail_sched_blocks
    )

    # modify the AFN surface object
    afn_surface_obj.WindowDoor_Opening_Factor_or_Crack_Factor = "1"
    afn_surface_obj.Ventilation_Control_Mode = "Constant"
    afn_surface_obj.Venting_Availability_Schedule_Name = avail_sched_obj_name

    # add the availability sensor
    aark.ep.generic.add_obj(
        idf,
        "EnergyManagementSystem:Sensor",
        Name=avail_sensor_obj_name,
        OutputVariable_or_OutputMeter_Index_Key_Name=avail_sched_obj_name,
        OutputVariable_or_OutputMeter_Name="Schedule Value",
    )

    # add the indoor air temperature sensor
    aark.ep.generic.add_obj(
        idf,
        "EnergyManagementSystem:Sensor",
        Name=Ta_sensor_obj_name,
        OutputVariable_or_OutputMeter_Index_Key_Name=zone_name,
        OutputVariable_or_OutputMeter_Name="Zone Mean Air Temperature",
    )

    # add the actuator
    aark.ep.generic.add_obj(
        idf,
        "EnergyManagementSystem:Actuator",
        Name=actuator_obj_name,
        Actuated_Component_Unique_Name=window_obj_name,
        Actuated_Component_Type="AirFlow Network Window/Door Opening",
        Actuated_Component_Control_Type="Venting Opening Factor",
    )

    # add the program
    aark.ep.generic.add_obj(
        idf,
        "EnergyManagementSystem:Program",
        Name=program_obj_name,
        **{f"Program_Line_{i}": line for i, line in enumerate(program_lines, start=1)},
    )

    # add the program to the calling manager
    add_program_to_calling_manager(idf, program_obj_name)


def apply_external_windows(
    idf: IDF, window_map: RoomMap, start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the external window openings.

    External windows refer to external glazed openings, including windows and
    patio doors, in habitable rooms.
    """
    for room_type, window_obj_names in window_map.items():
        for window_obj_name in window_obj_names:
            window_obj = aark.ep.generic.get_named_object(
                idf, "FenestrationSurface:Detailed", window_obj_name
            )
            zone_name = aark.ep.generic.get_zone_obj(window_obj).Name

            afn_surface_obj = aark.ep.afn.get_surface_obj(idf, window_obj_name)

            add_window(
                idf,
                afn_surface_obj,
                zone_name,
                room_type,
                start_month_day,
                end_month_day,
            )


def apply_internal_doors(
    idf: IDF, doors: Sequence[str], start_month_day: MonthDay, end_month_day: MonthDay
) -> None:
    """Apply the internal door openings.

    Internal doors refer to intra-dwelling doors.
    """
    # add the availability schedule
    avail_hourly_factors = get_avail_hourly_factors(STUDIO_TYPE)
    sched_obj_name = aark.tm59.prefix("internal_door_avail")
    sched_blocks = aark.ep.sched.make_compact_blocks(
        avail_hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "On/Off", *sched_blocks)

    for door_obj_name in doors:
        afn_surface_obj = aark.ep.afn.get_surface_obj(idf, door_obj_name)

        # modify the AFN surface object
        afn_surface_obj.WindowDoor_Opening_Factor_or_Crack_Factor = "1"
        afn_surface_obj.Ventilation_Control_Mode = "Constant"
        afn_surface_obj.Venting_Availability_Schedule_Name = sched_obj_name


def apply(
    idf: IDF,
    window_map: RoomMap,
    doors: Sequence[str],
    start_month_day: MonthDay = (1, 1),
    end_month_day: MonthDay = (12, 31),
) -> None:
    """Apply the window and door openings to the idf.

    `aark` requirements
    -------------------
    EnergyPlus version is 24.1 or later, with no `Space` object.

    Notes
    -----
    A key user input is `window_map` with the conceptual type:

    ```python
    dict[str, list[str]]
    ```

    Each key is a TM59 habitable room type, and each value is a list of external window
    names. `window_map` covers the whole model and is not grouped by dwelling. An example of
    `window_map` is:

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
    # validate aark assumptions
    aark.validation.ep.validate_ep_ver(idf)
    aark.validation.ep.validate_no_space(idf)

    # validate user inputs
    validate_window_map(idf, window_map)
    validate_doors(idf, doors)

    apply_external_windows(idf, window_map, start_month_day, end_month_day)
    apply_internal_doors(idf, doors, start_month_day, end_month_day)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_fenestration_afn_opening(idf: IDF, fenestration_obj_name: str) -> None:
    """Validate the AFN opening linkage needed to control a fenestration."""
    aark.ep.generic.get_named_object(
        idf, "FenestrationSurface:Detailed", fenestration_obj_name
    )
    afn_surface_obj = aark.ep.afn.get_surface_obj(idf, fenestration_obj_name)

    if not aark.ep.afn.is_opening_component(
        idf, str(afn_surface_obj.Leakage_Component_Name)
    ):
        raise ValueError(
            f"Fenestration has no Airflow Network opening component: {fenestration_obj_name}."
        )


def validate_window_map(idf: IDF, window_map: RoomMap) -> None:
    """Validate a window map for applying external window opening."""
    aark.tm59.utils.validate_room_map(window_map)

    invalid_room_types = set(window_map) - HABITABLE_ROOM_TYPES
    if invalid_room_types:
        raise ValueError(
            f"Invalid room types for window opening: {invalid_room_types}."
        )

    # NOTE: fast fail
    for window_obj_names in window_map.values():
        for window_obj_name in window_obj_names:
            validate_fenestration_afn_opening(idf, window_obj_name)


def validate_doors(idf: IDF, doors: Sequence[str]) -> None:
    """Validate a sequence of doors for applying internal door opening."""
    if not doors:
        raise ValueError(f"Empty doors: {doors}.")

    if isinstance(doors, str):
        raise TypeError(f"Invalid door sequence: {doors}.")

    # NOTE: fast fail
    for door_obj_name in doors:
        validate_fenestration_afn_opening(idf, door_obj_name)
