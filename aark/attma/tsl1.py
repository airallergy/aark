"""Create a complete minimal ATTMA TSL1 crack-infiltration AirflowNetwork."""

import math
from typing import TYPE_CHECKING

import aark.ep._pact
import aark.ep.field
import aark.ep.obj

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eppy.modeleditor import IDF

    type AirflowRecord = Mapping[str, str | Sequence[str]]


def _get_all_vals_by_record_key(
    airflow_records: Sequence[AirflowRecord], key: str
) -> tuple[str, ...]:
    """Get all values for a key across airflow records."""
    vals = []

    for airflow_record in airflow_records:
        if key not in airflow_record:
            continue

        val = airflow_record[key]
        if isinstance(val, str):
            vals.append(val)
        else:
            vals.extend(val)

    return tuple(vals)


def apply(
    idf: IDF,
    air_leakage_records: Sequence[AirflowRecord],
    wind_pressure_coeff_records: Sequence[AirflowRecord],
) -> None:
    """Apply the tested air leakage to the IDF.

    `aark` requirements
    -------------------
    EnergyPlus version is 24.1 or later, with no `Space` object or AirflowNetwork
    objects.

    Notes
    -----
    Both `air_leakage_records` and `wind_pressure_coeff_records` have the
    conceptual type:

    ```python
    list[dict[str, str | list[str]]]
    ```

    Each `air_leakage_record` represents one independently tested dwelling and
    contains its air leakage in m3 h-1 @ 50 Pa, airflow exponent, allocation surfaces,
    one side of each reciprocal internal-door pair and optional ambient doors. For
    example:

    ```python
    air_leakage_records = [
        {
            "air_leakage": "120",
            "airflow_exponent": "0.65",
            "allocation_surfaces": [
                "flat_1_north_wall",
                "flat_1_hall_bedroom_wall",
                "flat_1_hall_living_wall",
                "flat_1_to_flat_2_wall",
                "flat_1_to_corridor_wall",
            ],
            "internal_doors": ["flat_1_hall_bedroom_door", "flat_1_hall_living_door"],
        },
        {
            "air_leakage": "105",
            "airflow_exponent": "0.64",
            "allocation_surfaces": [
                "flat_2_south_wall",
                "flat_2_hall_bedroom_wall",
                "flat_2_to_flat_1_wall",
            ],
            "internal_doors": ["flat_2_hall_bedroom_door"],
            "ambient_doors": ["flat_2_store_door"],
        },
    ]
    ```

    The optional `ambient_doors` key lists the names of external doors serving garages
    or external stores thermally attached to the dwelling represented by the record.
    The outer surfaces of each space are excluded from the building envelope area
    calculation, and the space lies outside the tested internal volume. The fabric it
    shares with the dwelling is included in `allocation_surfaces`. These doors can
    complete the AirflowNetwork paths for the corresponding zones, each of which
    requires at least two paths.

    The records in `wind_pressure_coeff_records` collectively cover all outdoor
    allocation surfaces and the parent surfaces of all ambient doors. Each record
    provides a name, between 2 and 36 strictly ascending symmetric relative wind
    angles from 0° to 180°, one coefficient per angle, the external surfaces to which
    it applies and a reference height. All records must use the same angle sequence.
    For example:

    ```python
    wind_pressure_coeff_records = [
        {
            "name": "wall_floor_0",
            "ref_height": "10",
            "angles": ["0", "45", "90", "135", "180"],
            "coeffs": ["0.106", "0.042", "-0.145", "-0.148", "-0.084"],
            "external_surfaces": ["flat_1_north_wall", "flat_1_south_wall"],
        },
        {
            "name": "roof_floor_4",
            "ref_height": "10",
            "angles": ["0", "45", "90", "135", "180"],
            "coeffs": ["-0.219"] * 5,
            "external_surfaces": ["flat_9_roof"],
        },
    ]
    ```
    """
    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)
    aark.ep._pact.validate_no_space(idf)
    aark.ep._pact.validate_no_afn_objs(idf)

    # validate user inputs
    _validate_air_leakage_records(air_leakage_records, idf)
    _validate_wind_pressure_coeff_records(
        wind_pressure_coeff_records, idf, air_leakage_records
    )


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_airflow_record_texts(*texts: object) -> None:
    """Validate airflow record texts."""
    for text in texts:
        # texts must be strings
        if not isinstance(text, str):
            raise TypeError(f"Non-string record value: {text}.")

        # texts must not be empty or whitespace-only
        if not text.strip():
            raise ValueError(f"Empty or whitespace-only record value: {text}.")


def _validate_airflow_record_numbers(*numbers: object) -> None:
    """Validate airflow record numbers."""
    for number in numbers:
        # numbers must be numeric
        # NOTE: these values are typed as `str`, but not intentionally validated to
        #       allow `float` and `int`
        _number = float(str(number))

        # numbers must be finite
        if not math.isfinite(_number):
            raise ValueError(f"Non-finite record value: {number}.")


def _validate_airflow_record(
    airflow_record: AirflowRecord,
    textual_str_keys: set[str],
    numeric_str_keys: set[str],
    textual_sequence_keys: set[str],
    numeric_sequence_keys: set[str],
    optional_textual_sequence_keys: set[str],
) -> None:
    """Validate an airflow record."""
    required_keys = (
        textual_str_keys
        | numeric_str_keys
        | textual_sequence_keys
        | numeric_sequence_keys
    )
    valid_keys = required_keys | optional_textual_sequence_keys

    # the record must contain all required keys and only allowed keys
    if not required_keys <= set(airflow_record) <= valid_keys:
        raise ValueError(f"Invalid record keys: {airflow_record.keys()}.")

    for key, val in airflow_record.items():
        if key in textual_str_keys:
            # the textual value must be valid
            _validate_airflow_record_texts(val)

        elif key in numeric_str_keys:
            # the numeric value must be valid
            _validate_airflow_record_numbers(val)

        else:
            # sequences must not be strings
            if isinstance(val, str):
                raise TypeError(f"Sequence record value must not be a string: {val}.")

            # sequences must not be empty
            if not val:
                raise ValueError(f"Empty sequence record value: {val}.")

            if key in textual_sequence_keys | optional_textual_sequence_keys:
                # the textual values must be valid
                _validate_airflow_record_texts(*val)

            else:
                # the numeric values must be valid
                _validate_airflow_record_numbers(*val)


def _validate_air_leakage(air_leakage: str) -> None:
    """Validate a positive air leakage value."""
    if float(air_leakage) <= 0:
        raise ValueError(f"Non-positive value for `air_leakage`: {air_leakage}.")


def _validate_air_leakage_airflow_exponent(airflow_exponent: str) -> None:
    """Validate an airflow exponent between 0.5 and 1."""
    if not 0.5 <= float(airflow_exponent) <= 1:
        raise ValueError(
            f"Value for `airflow_exponent` is not between 0.5 and 1: {airflow_exponent}."
        )


def _validate_air_leakage_allocation_surfaces(
    allocation_surface_names: Sequence[str], idf: IDF
) -> None:
    """Validate allocation surfaces in one air leakage record."""
    has_non_adiabatic_surface = False
    internal_surface_names = []
    for surface_name in allocation_surface_names:
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", surface_name
        )
        outside_boundary_condition = surface_obj.Outside_Boundary_Condition
        normalised_outside_boundary_condition = aark.ep.field.normalise(
            outside_boundary_condition, surface_obj, "Outside_Boundary_Condition"
        )

        # allocation surfaces must have supported outside boundary conditions
        if normalised_outside_boundary_condition not in {
            "ADIABATIC",
            "OUTDOORS",
            "SURFACE",
        }:
            raise ValueError(
                f"Unsupported outside boundary condition for allocation surfaces: {outside_boundary_condition}."
            )

        if normalised_outside_boundary_condition != "ADIABATIC":
            has_non_adiabatic_surface = True
        if normalised_outside_boundary_condition == "SURFACE":
            internal_surface_names.append(surface_name)

    # at least one allocation surface must be non-adiabatic
    if not has_non_adiabatic_surface:
        raise ValueError(
            f"No non-adiabatic allocation surfaces: {allocation_surface_names}."
        )

    # only one side of each internal allocation surface must be supplied
    aark.ep.obj.validate_no_other_surface(
        idf, "BuildingSurface:Detailed", *internal_surface_names
    )


def _validate_air_leakage_ambient_doors(
    ambient_door_names: Sequence[str], allocation_surface_names: Sequence[str], idf: IDF
) -> None:
    """Validate ambient doors in one air leakage record."""
    for door_name in ambient_door_names:
        door_obj = aark.ep.obj.get_named(idf, "FenestrationSurface:Detailed", door_name)
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", door_obj.Building_Surface_Name
        )
        zone_obj = aark.ep.obj.get_zone(surface_obj)

        # ambient door parent surfaces must be outdoors
        if not aark.ep.field.equal(
            "Outdoors", surface_obj, "Outside_Boundary_Condition"
        ):
            raise ValueError(
                f"Ambient door parent surface is not outdoors: {surface_obj.Outside_Boundary_Condition}."
            )

        zone_surface_objs = [
            surface_obj
            for surface_obj in idf.idfobjects["BuildingSurface:Detailed"]
            if surface_obj.Zone_Name == zone_obj.Name
        ]

        # ambient zone external surfaces must not be allocation surfaces
        zone_external_surface_names = {
            surface_obj.Name
            for surface_obj in zone_surface_objs
            if aark.ep.field.equal(
                "Outdoors", surface_obj, "Outside_Boundary_Condition"
            )
        }
        if zone_external_surface_names & set(allocation_surface_names):
            raise ValueError(
                f"Ambient door zone has outdoor allocation surfaces: {door_name}."
            )

        # ambient zones must have an internal allocation surface pair
        zone_internal_surface_objs = [
            surface_obj
            for surface_obj in zone_surface_objs
            if aark.ep.field.equal("Surface", surface_obj, "Outside_Boundary_Condition")
        ]
        zone_internal_surface_names = {
            surface_obj.Name for surface_obj in zone_internal_surface_objs
        }
        zone_other_internal_surface_names = {
            surface_obj.Outside_Boundary_Condition_Object
            for surface_obj in zone_internal_surface_objs
        }
        if not (
            (zone_internal_surface_names | zone_other_internal_surface_names)
            & set(allocation_surface_names)
        ):
            raise ValueError(
                f"Ambient door zone has no internal allocation surface: {door_name}."
            )


def _validate_air_leakage_record(air_leakage_record: AirflowRecord, idf: IDF) -> None:
    """Validate one air leakage record."""
    # the record must have a valid structure
    _validate_airflow_record(
        air_leakage_record,
        set(),
        {"air_leakage", "airflow_exponent"},
        {"allocation_surfaces", "internal_doors"},
        set(),
        {"ambient_doors"},
    )

    air_leakage = air_leakage_record["air_leakage"]
    airflow_exponent = air_leakage_record["airflow_exponent"]
    allocation_surface_names = air_leakage_record["allocation_surfaces"]
    ambient_door_names = air_leakage_record.get("ambient_doors", ())

    # the air leakage value must be valid
    _validate_air_leakage(str(air_leakage))

    # the airflow exponent must be valid
    _validate_air_leakage_airflow_exponent(str(airflow_exponent))

    # the allocation surface sequence must be valid
    _validate_air_leakage_allocation_surfaces(allocation_surface_names, idf)

    # the ambient door sequence must be valid
    _validate_air_leakage_ambient_doors(
        ambient_door_names, allocation_surface_names, idf
    )


def _validate_air_leakage_records(
    air_leakage_records: Sequence[AirflowRecord], idf: IDF
) -> None:
    """Validate all air leakage records."""
    # the record sequence must not be empty
    if not air_leakage_records:
        raise ValueError(f"Empty air leakage records: {air_leakage_records}.")

    for air_leakage_record in air_leakage_records:
        # each air leakage record must be valid
        _validate_air_leakage_record(air_leakage_record, idf)

    allocation_surface_names = _get_all_vals_by_record_key(
        air_leakage_records, "allocation_surfaces"
    )
    internal_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "internal_doors"
    )
    ambient_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "ambient_doors"
    )

    # allocation surface names must be unique and identify detailed building surfaces
    aark.ep.obj.validate_obj_names(
        idf, "BuildingSurface:Detailed", *allocation_surface_names
    )

    # internal door names must be unique and identify fenestration surfaces
    aark.ep.obj.validate_obj_names(
        idf, "FenestrationSurface:Detailed", *internal_door_names
    )

    # only one side of each internal door must be supplied
    aark.ep.obj.validate_no_other_surface(
        idf, "FenestrationSurface:Detailed", *internal_door_names
    )

    # ambient door names must be unique and identify fenestration surfaces
    aark.ep.obj.validate_obj_names(
        idf, "FenestrationSurface:Detailed", *ambient_door_names
    )


def _validate_wind_pressure_coeff_ref_height(ref_height: str) -> None:
    """Validate a positive reference height."""
    if float(ref_height) <= 0:
        raise ValueError(f"Non-positive `ref_height`: {ref_height}.")


def _validate_wind_pressure_coeff_angles(angles: Sequence[str]) -> None:
    """Validate angles in one wind pressure coefficient record."""
    # the angle count must be between 2 and 36
    if not 2 <= len(angles) <= 36:
        raise ValueError(f"Angle count is not between 2 and 36: {len(angles)}.")

    _angles = tuple(float(angle) for angle in angles)

    # angle endpoints must be 0° and 180°
    if _angles[0] != 0 or _angles[-1] != 180:
        raise ValueError(f"Angle endpoints are not 0° and 180°: {_angles}.")

    # angles must be strictly increasing
    if any(_angles[i] >= _angles[i + 1] for i in range(len(_angles) - 1)):
        raise ValueError(f"Angles are not strictly increasing: {_angles}.")


def _validate_wind_pressure_coeff_external_surfaces(
    external_surface_names: Sequence[str], idf: IDF
) -> None:
    """Validate that wind pressure coefficient surfaces are outdoors."""
    # NOTE: fast fail
    for surface_name in external_surface_names:
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", surface_name
        )

        if not aark.ep.field.equal(
            "Outdoors", surface_obj, "Outside_Boundary_Condition"
        ):
            raise ValueError(
                f"External surface is not outdoors: {surface_obj.Outside_Boundary_Condition}."
            )


def _validate_wind_pressure_coeff_record(
    wind_pressure_coeff_record: AirflowRecord, idf: IDF
) -> None:
    """Validate one wind pressure coefficient record."""
    # the record must have valid keys and values
    _validate_airflow_record(
        wind_pressure_coeff_record,
        {"name"},
        {"ref_height"},
        {"external_surfaces"},
        {"angles", "coeffs"},
        set(),
    )

    ref_height = wind_pressure_coeff_record["ref_height"]
    angles = wind_pressure_coeff_record["angles"]
    coeffs = wind_pressure_coeff_record["coeffs"]
    external_surface_names = wind_pressure_coeff_record["external_surfaces"]

    # the reference height must be valid
    _validate_wind_pressure_coeff_ref_height(str(ref_height))

    # the angle sequence must be valid
    _validate_wind_pressure_coeff_angles(angles)

    # coefficient and angle counts must match
    if len(coeffs) != len(angles):
        raise ValueError(
            f"Coefficient and angle counts differ: {(len(coeffs), len(angles))}."
        )

    # the external surface sequence must be valid
    _validate_wind_pressure_coeff_external_surfaces(external_surface_names, idf)


def _validate_wind_pressure_coeff_records(
    wind_pressure_coeff_records: Sequence[AirflowRecord],
    idf: IDF,
    air_leakage_records: Sequence[AirflowRecord],
) -> None:
    """Validate all wind pressure coefficient records."""
    # the record sequence must not be empty
    if not wind_pressure_coeff_records:
        raise ValueError(
            f"Empty wind pressure coefficient records: {wind_pressure_coeff_records}."
        )

    for wind_pressure_coeff_record in wind_pressure_coeff_records:
        # each wind pressure coefficient record must be valid
        _validate_wind_pressure_coeff_record(wind_pressure_coeff_record, idf)

    record_names = _get_all_vals_by_record_key(wind_pressure_coeff_records, "name")
    external_surface_names = _get_all_vals_by_record_key(
        wind_pressure_coeff_records, "external_surfaces"
    )

    unique_record_names = set(record_names)
    normalised_record_names = {
        record_name.strip().upper() for record_name in unique_record_names
    }

    # record names must be unique
    if len(record_names) != len(unique_record_names):
        raise ValueError(
            f"Duplicate names in wind pressure coefficient records: {record_names}."
        )

    # unique record names must not be equivalent
    if len(unique_record_names) != len(normalised_record_names):
        raise ValueError(
            f"Equivalent names in wind pressure coefficient records: {record_names}."
        )

    # external surface names must be unique and identify detailed building surfaces
    aark.ep.obj.validate_obj_names(
        idf, "BuildingSurface:Detailed", *external_surface_names
    )

    # all records must use the same angle sequence
    angle_sequences = {
        tuple(map(float, wind_pressure_coeff_record["angles"]))
        for wind_pressure_coeff_record in wind_pressure_coeff_records
    }

    if len(angle_sequences) != 1:
        raise ValueError(
            f"Found multiple angles in wind pressure coefficient records: {angle_sequences}."
        )

    # every outdoor surface must have wind pressure coefficients
    allocation_surface_names = _get_all_vals_by_record_key(
        air_leakage_records, "allocation_surfaces"
    )
    ambient_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "ambient_doors"
    )

    external_allocation_surface_names = {
        surface_name
        for surface_name in allocation_surface_names
        if aark.ep.field.equal(
            "Outdoors",
            aark.ep.obj.get_named(idf, "BuildingSurface:Detailed", surface_name),
            "Outside_Boundary_Condition",
        )
    }
    ambient_surface_names = {
        aark.ep.obj.get_named(
            idf, "FenestrationSurface:Detailed", door_name
        ).Building_Surface_Name
        for door_name in ambient_door_names
    }

    missing_surface_names = (
        external_allocation_surface_names | ambient_surface_names
    ) - set(external_surface_names)
    if missing_surface_names:
        raise ValueError(
            f"Missing wind pressure coefficients for outdoor surfaces: {missing_surface_names}."
        )
