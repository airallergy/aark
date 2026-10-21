"""TM59:2017 Section 3.3 and ADO:2021 Paragraph 2.6 window and door openings."""

from typing import TYPE_CHECKING

import aark._utils
import aark.ep._pact
import aark.ep.afn
import aark.ep.ems
import aark.ep.field
import aark.ep.obj
import aark.ep.sched
import aark.tm59._utils
from aark._utils import YEAR_END_MONTH_DAY, YEAR_START_MONTH_DAY
from aark.tm59.data import (
    AWAKE_END_HOUR,
    AWAKE_START_HOUR,
    HABITABLE_ROOM_TYPES,
    INTERNAL_GAIN_PROFILES,
    WINDOW_OPENING_THRESHOLD,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF

    from aark._utils import MonthDay
    from aark.tm59._utils import RoomMap


_ADO_DAY_VENT_MIN_THRESHOLD = WINDOW_OPENING_THRESHOLD
_ADO_DAY_VENT_MAX_THRESHOLD = 26  # °C
_ADO_NIGHT_VENT_THRESHOLD = 23  # °C


def _get_window_avail_hourly_factors(
    room_type: str, asleep_closed: bool, ado: bool
) -> tuple[str, ...]:
    """Get hourly window availability factors."""
    # default availability follows occupancy
    occupancy_hourly_factors = INTERNAL_GAIN_PROFILES.get_hourly_factors(
        "occupancy", room_type
    )
    hourly_factors = tuple(
        "0" if factor == "0" else "1" for factor in occupancy_hourly_factors
    )

    if asleep_closed:
        # keep windows unavailable during sleeping hours
        hourly_factors = tuple(
            factor if AWAKE_START_HOUR <= hour < AWAKE_END_HOUR else "0"
            for hour, factor in enumerate(hourly_factors)
        )
    elif ado:
        # allow opening during sleeping hours regardless of occupancy
        hourly_factors = tuple(
            factor if AWAKE_START_HOUR <= hour < AWAKE_END_HOUR else "1"
            for hour, factor in enumerate(hourly_factors)
        )

    return hourly_factors


def _get_door_avail_hourly_factors(awake_closed: bool) -> tuple[str, ...]:
    """Get hourly internal door availability factors."""
    hourly_factors = tuple(
        "1" if AWAKE_START_HOUR <= hour < AWAKE_END_HOUR else "0" for hour in range(24)
    )

    if awake_closed:
        hourly_factors = ("0",) * 24

    return hourly_factors


def _add_ado_night_flag(idf: IDF, zone_name: str, night_vent_flag_name: str) -> None:
    """Add an ADO night ventilation flag and its initialiser."""
    init_program_obj_name = aark.tm59._utils.erl_uid("night_vent_flag_init", zone_name)
    init_calling_manager_obj_name = aark.tm59._utils.prefix("night_vent_init_manager")

    aark.ep.obj.add(
        idf,
        "EnergyManagementSystem:GlobalVariable",
        Erl_Variable_1_Name=night_vent_flag_name,
    )

    aark.ep.ems.add_program(
        idf, init_program_obj_name, f"SET {night_vent_flag_name} = 0"
    )

    aark.ep.ems.add_program_to_calling_manager(
        idf, init_calling_manager_obj_name, "BeginNewEnvironment", init_program_obj_name
    )


def _add_window(
    idf: IDF,
    afn_surface_obj: EpBunch,
    zone_name: str,
    room_type: str,
    asleep_closed: bool,
    ado: bool,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add control for the window."""
    window_name = afn_surface_obj.Surface_Name
    avail_sched_obj_name = aark.tm59._utils.prefix(f"window_avail_{room_type}")
    avail_sensor_obj_name = aark.tm59._utils.erl_uid("window_avail", room_type)
    Ta_sensor_obj_name = aark.tm59._utils.erl_uid("Ta", zone_name)
    actuator_obj_name = aark.tm59._utils.erl_uid("vent_factor", window_name)
    program_obj_name = aark.tm59._utils.erl_uid("vent", window_name)

    if ado:
        avail_sched_obj_name += "_ado"
        avail_sensor_obj_name += "_ado"

    if asleep_closed:
        avail_sched_obj_name += "_asleep_closed"
        avail_sensor_obj_name += "_asleep_closed"

    # compose program lines
    max_vent_factor = aark.ep.field.with_default(
        afn_surface_obj.WindowDoor_Opening_Factor_or_Crack_Factor,
        afn_surface_obj,
        "WindowDoor_Opening_Factor_or_Crack_Factor",
    )

    if ado:
        night_vent_flag_name = aark.tm59._utils.erl_uid("night_vent_flag", zone_name)
        _add_ado_night_flag(idf, zone_name, night_vent_flag_name)

        program_lines = [
            f"IF (Hour == {AWAKE_END_HOUR}) && (TimeStepNum == 1)",
            f"IF {Ta_sensor_obj_name} > {_ADO_NIGHT_VENT_THRESHOLD}",
            f"SET {night_vent_flag_name} = 1",
            "ELSE",
            f"SET {night_vent_flag_name} = 0",
            "ENDIF",
            "ENDIF",
            f"IF {avail_sensor_obj_name} > 0",
            f"IF (Hour >= {AWAKE_END_HOUR}) || (Hour < {AWAKE_START_HOUR})",
            f"SET vent_frac = {night_vent_flag_name}",
            "ELSE",
            f"IF {Ta_sensor_obj_name} > {_ADO_DAY_VENT_MAX_THRESHOLD}",
            "SET vent_frac = 1",
            f"ELSEIF {Ta_sensor_obj_name} <= {_ADO_DAY_VENT_MIN_THRESHOLD}",
            "SET vent_frac = 0",
            "ELSE",
            f"SET vent_frac = ({Ta_sensor_obj_name} - {_ADO_DAY_VENT_MIN_THRESHOLD}) / {_ADO_DAY_VENT_MAX_THRESHOLD - _ADO_DAY_VENT_MIN_THRESHOLD}",
            "ENDIF",
            "ENDIF",
            "ELSE",
            "SET vent_frac = 0",
            "ENDIF",
            f"SET {actuator_obj_name} = {max_vent_factor} * vent_frac",
        ]
    else:
        program_lines = [
            f"IF {avail_sensor_obj_name} > 0",
            f"IF {Ta_sensor_obj_name} > {WINDOW_OPENING_THRESHOLD}",
            f"SET {actuator_obj_name} = {max_vent_factor}",
            "ELSE",
            f"SET {actuator_obj_name} = 0",
            "ENDIF",
            "ELSE",
            f"SET {actuator_obj_name} = 0",
            "ENDIF",
        ]

    # add the availability schedule
    avail_hourly_factors = _get_window_avail_hourly_factors(
        room_type, asleep_closed, ado
    )
    avail_sched_blocks = aark.tm59._utils.make_compact_blocks(
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
    aark.ep.ems.add_program(idf, program_obj_name, *program_lines)
    # add the program to the calling manager
    aark.ep.ems.add_program_to_calling_manager(
        idf,
        aark.tm59._utils.prefix("window_vent"),
        "BeginTimestepBeforePredictor",
        program_obj_name,
    )


def _add_door(
    idf: IDF,
    afn_surface_obj: EpBunch,
    awake_closed: bool,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
) -> None:
    """Add control for the door."""
    sched_obj_name = aark.tm59._utils.prefix("internal_door_avail")

    if awake_closed:
        sched_obj_name += "_awake_closed"

    # add the availability schedule
    avail_hourly_factors = _get_door_avail_hourly_factors(awake_closed)
    sched_blocks = aark.tm59._utils.make_compact_blocks(
        avail_hourly_factors, start_month_day, end_month_day
    )
    aark.ep.sched.add_compact_obj(idf, sched_obj_name, "On/Off", *sched_blocks)

    # modify the afn surface object
    afn_surface_obj.Ventilation_Control_Mode = "Constant"
    afn_surface_obj.Venting_Availability_Schedule_Name = sched_obj_name


def _apply_external_windows(
    idf: IDF,
    window_map: RoomMap,
    ado: bool,
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    asleep_closed_windows: Sequence[str],
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
                window_name in asleep_closed_windows,
                ado,
                start_month_day,
                end_month_day,
            )


def _apply_internal_doors(
    idf: IDF,
    door_names: Sequence[str],
    start_month_day: MonthDay,
    end_month_day: MonthDay,
    awake_closed_doors: Sequence[str],
) -> None:
    """Apply the internal door openings.

    Internal doors refer to intra-dwelling doors.
    """
    for door_name in door_names:
        afn_surface_obj = aark.ep.afn.get_surface_obj(idf, door_name)

        _add_door(
            idf,
            afn_surface_obj,
            door_name in awake_closed_doors,
            start_month_day,
            end_month_day,
        )


def apply(
    idf: IDF,
    window_map: RoomMap,
    doors: Sequence[str],
    ado: bool = False,
    start_month_day: MonthDay = YEAR_START_MONTH_DAY,
    end_month_day: MonthDay = YEAR_END_MONTH_DAY,
    asleep_closed_windows: Sequence[str] = (),
    awake_closed_doors: Sequence[str] = (),
) -> None:
    """Apply the window and door openings to the IDF.

    `aark` requirements
    -------------------
    EnergyPlus version is 24.1 or later, with no `Space` object.

    Parameters
    ----------
    idf : IDF
        IDF to receive window and door opening controls.
    window_map : RoomMap
        TM59 habitable room types mapped to names of one or more
        `FenestrationSurface:Detailed` objects in `idf` representing external windows.
        The mapping covers the whole model and is not grouped by dwelling. For example:

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
    doors : Sequence[str]
        Names of `FenestrationSurface:Detailed` objects in `idf` representing internal
        doors. For example:

        ```python
        doors = [
            "flat_1_living-kitchen_door",
            "flat_2_bedroom-kitchen_door",
        ]
        ```
    ado : bool, optional
        Set `ado=True` to use Approved Document O 2021 window opening controls,
        defaulting to `False`.
    start_month_day, end_month_day : MonthDay, optional
        Inclusive active period as `(month, day)` pairs, defaulting to the whole year.
        The start must not be after the end. Windows and doors are closed outside this
        period.
    asleep_closed_windows : Sequence[str], optional
        Window names from `window_map` to keep closed from 23:00 to 08:00, defaulting to
        an empty sequence. TM59 models windows as open when the room is occupied and its
        internal dry bulb temperature exceeds 22 °C, subject to opening restrictions. By
        default, this applies throughout occupied hours, including overnight.
    awake_closed_doors : Sequence[str], optional
        Door names from `doors` to keep closed throughout, defaulting to an empty
        sequence. TM59 allows internal doors to remain open during the day but requires
        closure when occupants are sleeping. By default, listed doors are open from
        08:00 to 23:00 and closed otherwise.
    """
    # TODO: support closed, secure and maximum opening factors, with
    #       `0 <= secure_vent_factor <= max_vent_factor`, then add
    #       `unoccupied_open_windows` for tm59 and ado

    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)
    aark.ep._pact.validate_no_space(idf)

    # validate user inputs
    _validate_window_map(idf, window_map)
    _validate_doors(idf, doors)
    _validate_asleep_closed_windows(window_map, asleep_closed_windows)
    _validate_awake_closed_doors(doors, awake_closed_doors)
    aark._utils.validate_month_days(start_month_day, end_month_day)

    _apply_external_windows(
        idf, window_map, ado, start_month_day, end_month_day, asleep_closed_windows
    )
    _apply_internal_doors(
        idf, doors, start_month_day, end_month_day, awake_closed_doors
    )


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
    """Validate one sequence of doors."""
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


def _validate_asleep_closed_windows(
    window_map: RoomMap, asleep_closed_windows: Sequence[str]
) -> None:
    """Validate that windows closed during sleeping hours are in the window map."""
    window_names = {name for names in window_map.values() for name in names}
    unmapped_windows = set(asleep_closed_windows) - window_names

    if unmapped_windows:
        raise ValueError(
            f"Unknown windows for closure during sleeping hours: {unmapped_windows}."
        )


def _validate_awake_closed_doors(
    doors: Sequence[str], awake_closed_doors: Sequence[str]
) -> None:
    """Validate that doors closed during non-sleeping hours are in the door sequence."""
    unlisted_doors = set(awake_closed_doors) - set(doors)

    if unlisted_doors:
        raise ValueError(
            f"Unknown doors for closure during non-sleeping hours: {unlisted_doors}."
        )
