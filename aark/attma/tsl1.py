"""Create a complete minimal ATTMA TSL1 crack-infiltration AirflowNetwork."""

import itertools
import math
import warnings
from typing import TYPE_CHECKING

import aark._utils
import aark.ep._pact
import aark.ep.field
import aark.ep.obj
from aark.ep.afn import (
    REF_AIR_DENSITY,
    REF_HUMIDITY_RATIO,
    REF_PRESSURE,
    REF_TEMPERATURE,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eppy.modeleditor import IDF

    type AirflowRecord = Mapping[str, str | Sequence[str]]


_SHARED_AIR_PERMEABILITY_REL_TOLERANCE = 0.3


def prefix(s: str) -> str:
    """Prepend the ATTMA TSL1 namespace to a string."""
    p = aark._utils.prefix("attma_tsl1_")

    if not s:
        raise ValueError(f"Empty string: {s}.")

    if s.upper().startswith(p.upper()):
        raise ValueError(f"Prefix already exists: {s}.")

    return f"{p}{s}"


def _uid(*args: str) -> str:
    """Build a standard `aark`-generated UID."""
    args = tuple(arg for arg in args if arg)

    if not args:
        raise ValueError(f"Empty UID arguments: {args}.")

    return prefix("_".join(args))


def _get_all_vals_by_record_key(
    airflow_records: Sequence[AirflowRecord], key: str
) -> tuple[str, ...]:
    """Get all values for a key across airflow records."""
    all_vals = []

    for airflow_record in airflow_records:
        if key not in airflow_record:
            continue

        val = airflow_record[key]
        if isinstance(val, str):
            all_vals.append(val)
        else:
            all_vals.extend(val)

    return tuple(all_vals)


def _group_surface_pairs(
    air_leakage_records: Sequence[AirflowRecord],
    idf: IDF,
    surface_name2area: Mapping[str, float],
) -> tuple[dict[str, str], list[list[tuple[str, str]]]]:
    """Group shared reciprocal surface pairs by unordered dwelling pair."""
    # copy allocation surfaces for destructive pair discovery
    all_allocation_surface_names = list(
        _get_all_vals_by_record_key(air_leakage_records, "allocation_surfaces")
    )
    surface2other_surface_name = {}

    # find all shared reciprocal surface pairs
    while all_allocation_surface_names:
        surface_name = all_allocation_surface_names.pop(0)
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", surface_name
        )

        # only interzone surfaces can have reciprocal allocation surfaces
        if not aark.ep.field.equal(
            "Surface", surface_obj, "Outside_Boundary_Condition"
        ):
            continue

        # the reciprocal surface must also be allocated
        other_surface_name = surface_obj.Outside_Boundary_Condition_Object
        if other_surface_name not in all_allocation_surface_names:
            continue

        # remove the other side
        all_allocation_surface_names.remove(other_surface_name)

        # reciprocal surface areas must agree
        area = surface_name2area[surface_name]
        other_area = surface_name2area[other_surface_name]
        if not math.isclose(area, other_area):
            raise ValueError(
                f"Different areas for shared surfaces: {area, other_area}."
            )

        # map the lexicographically smaller one to the larger one
        left, right = sorted((surface_name, other_surface_name))
        surface2other_surface_name[left] = right

    # group surface pairs by unordered dwelling pair
    surface_name_pair_groups = []
    for air_leakage_record, other_air_leakage_record in itertools.combinations(
        air_leakage_records, 2
    ):
        # get the surfaces owned by each dwelling
        allocation_surface_names = air_leakage_record["allocation_surfaces"]
        other_allocation_surface_names = other_air_leakage_record["allocation_surfaces"]

        # select shared pairs spanning this dwelling pair
        surface_name_pairs = [
            (surface_name, other_surface_name)
            for surface_name, other_surface_name in surface2other_surface_name.items()
            if (
                (surface_name in allocation_surface_names)
                and (other_surface_name in other_allocation_surface_names)
            )
            or (
                (other_surface_name in allocation_surface_names)
                and (surface_name in other_allocation_surface_names)
            )
        ]

        if surface_name_pairs:
            surface_name_pair_groups.append(surface_name_pairs)

    return surface2other_surface_name, surface_name_pair_groups


def _allocate_air_leakage_parse(
    air_leakage_records: Sequence[AirflowRecord], idf: IDF
) -> tuple[dict[str, float], set[str], dict[str, str], list[list[tuple[str, str]]]]:
    """Parse the surface data required to allocate air leakage."""
    surface_name2area = {}
    adiabatic_surface_names = set()

    # collect surface areas and adiabatic surfaces
    for air_leakage_record in air_leakage_records:
        allocation_surface_names = air_leakage_record["allocation_surfaces"]
        for surface_name in allocation_surface_names:
            surface_obj = aark.ep.obj.get_named(
                idf, "BuildingSurface:Detailed", surface_name
            )
            surface_name2area[surface_name] = float(surface_obj.area)

            if aark.ep.field.equal(
                "Adiabatic", surface_obj, "Outside_Boundary_Condition"
            ):
                adiabatic_surface_names.add(surface_name)

    # group reciprocal surfaces shared by dwelling pairs
    surface2other_surface_name, surface_name_pair_groups = _group_surface_pairs(
        air_leakage_records, idf, surface_name2area
    )

    return (
        surface_name2area,
        adiabatic_surface_names,
        surface2other_surface_name,
        surface_name_pair_groups,
    )


def _allocate_air_leakage_init(
    air_leakage_records: Sequence[AirflowRecord], surface_name2area: Mapping[str, float]
) -> tuple[dict[str, float], dict[str, float]]:
    """Initialise air leakage allocation."""
    surface_name2air_permeability: dict[str, float] = {}
    surface_name2airflow_exponent: dict[str, float] = {}

    for air_leakage_record in air_leakage_records:
        air_leakage = float(str(air_leakage_record["air_leakage"]))
        airflow_exponent = float(str(air_leakage_record["airflow_exponent"]))
        allocation_surface_names = air_leakage_record["allocation_surfaces"]

        # calculate the initial uniform air permeability
        total_area = sum(
            surface_name2area[surface_name] for surface_name in allocation_surface_names
        )
        air_permeability = air_leakage / total_area

        # assign the initial parameters to each surface
        for surface_name in allocation_surface_names:
            surface_name2air_permeability[surface_name] = air_permeability
            surface_name2airflow_exponent[surface_name] = airflow_exponent

    return surface_name2air_permeability, surface_name2airflow_exponent


def _fit_shared_exponent(n1: float, n2: float, ap1: float, ap2: float) -> float:
    """Fit one 50 Pa-anchored exponent to the mean leakage-intensity curve."""
    dp50 = 50
    ap50 = (ap1 + ap2) / 2

    sum_xy = 0.0
    sum_x2 = 0.0
    n_pressures = 100

    # TODO: consider sampling below 1 Pa to represent normal operation
    for i in range(n_pressures):
        # sample logarithmically spaced pressure differentials
        dp = dp50 ** (i / (n_pressures - 1))

        # calculate the mean target leakage intensity `ap` at `dp`
        ap = 0.5 * (ap1 * (dp / dp50) ** n1 + ap2 * (dp / dp50) ** n2)

        # transform the anchored power law to `y = n x`
        x = math.log(dp / dp50)
        y = math.log(ap / ap50)

        # accumulate the ordinary least-squares terms
        sum_xy += x * y
        sum_x2 += x**2

    # solve for the fitted slope
    return sum_xy / sum_x2


def _allocate_air_leakage_reconcile(
    surface_name2air_permeability: dict[str, float],
    surface_name2airflow_exponent: dict[str, float],
    surface_name_pair_groups: list[list[tuple[str, str]]],
) -> None:
    """Reconcile air leakage for shared surfaces."""
    for surface_name_pairs in surface_name_pair_groups:
        # surface pairs in the same dwelling pair group have identical initial parameters
        # use the first surface pair as a reference for surface pairs
        ref_surface_name, ref_other_surface_name = surface_name_pairs[0]

        # get the initial parameters
        air_permeability = surface_name2air_permeability[ref_surface_name]
        other_air_permeability = surface_name2air_permeability[ref_other_surface_name]

        exponent = surface_name2airflow_exponent[ref_surface_name]
        other_exponent = surface_name2airflow_exponent[ref_other_surface_name]

        # warn about a substantial initial permeability difference
        air_permeability_rel_diff = abs(air_permeability - other_air_permeability) / (
            (air_permeability + other_air_permeability) / 2
        )
        if air_permeability_rel_diff > _SHARED_AIR_PERMEABILITY_REL_TOLERANCE:
            warnings.warn(
                f"Air permeability difference between shared surfaces exceeds {_SHARED_AIR_PERMEABILITY_REL_TOLERANCE:.0%}: {surface_name_pairs}.",
                stacklevel=3,
            )

        # derive shared parameters
        shared_air_permeability = (air_permeability + other_air_permeability) / 2
        shared_exponent = _fit_shared_exponent(
            exponent, other_exponent, air_permeability, other_air_permeability
        )

        # assign the shared parameters to every surface pair
        for surface_name, other_surface_name in surface_name_pairs:
            surface_name2air_permeability[surface_name] = shared_air_permeability
            surface_name2air_permeability[other_surface_name] = shared_air_permeability
            surface_name2airflow_exponent[surface_name] = shared_exponent
            surface_name2airflow_exponent[other_surface_name] = shared_exponent


def _allocate_air_leakage_reallocate(
    surface_name2air_permeability: dict[str, float],
    air_leakage_records: Sequence[AirflowRecord],
    surface_name2area: Mapping[str, float],
    surface2other_surface_name: Mapping[str, str],
) -> None:
    """Reallocate remaining air leakage."""
    # identify both sides of every shared surface pair
    all_shared_surface_names = set(surface2other_surface_name) | set(
        surface2other_surface_name.values()
    )

    for air_leakage_record in air_leakage_records:
        air_leakage = float(str(air_leakage_record["air_leakage"]))
        allocation_surface_names = set(air_leakage_record["allocation_surfaces"])

        shared_surface_names = allocation_surface_names & all_shared_surface_names
        non_shared_surface_names = allocation_surface_names - shared_surface_names

        # calculate the remaining leakage
        shared_leakage = sum(
            surface_name2air_permeability[surface_name]
            * surface_name2area[surface_name]
            for surface_name in shared_surface_names
        )
        remaining_leakage = air_leakage - shared_leakage

        if non_shared_surface_names:
            if math.isclose(remaining_leakage, 0, rel_tol=0, abs_tol=1e-8):
                # require non-zero remaining leakage when there are non-shared surfaces
                raise ValueError(
                    f"Approximately zero leakage remainder despite non-shared surfaces: {remaining_leakage}."
                )

            if remaining_leakage < 0:
                # require non-negative remaining leakage when there are non-shared surfaces
                raise ValueError(
                    f"Negative leakage remainder after shared-surface reconciliation: {remaining_leakage}."
                )

            # distribute the remainder uniformly by surface area
            total_non_shared_area = sum(
                surface_name2area[surface_name]
                for surface_name in non_shared_surface_names
            )
            remaining_air_permeability = remaining_leakage / total_non_shared_area

            for surface_name in non_shared_surface_names:
                surface_name2air_permeability[surface_name] = remaining_air_permeability

        elif not math.isclose(remaining_leakage, 0, rel_tol=0, abs_tol=1e-8):
            # require zero remaining leakage when every allocation surface is shared
            raise ValueError(
                f"Non-zero leakage remainder with no non-shared surfaces: {remaining_leakage}."
            )


def _allocate_air_leakage(
    air_leakage_records: Sequence[AirflowRecord], idf: IDF
) -> dict[str, tuple[float, float]]:
    """Allocate air leakage to surfaces."""
    # parse surface data
    (
        surface_name2area,
        adiabatic_surface_names,
        surface2other_surface_name,
        surface_name_pair_groups,
    ) = _allocate_air_leakage_parse(air_leakage_records, idf)

    # step 1 - assign initial air permeability and exponent to each surface
    surface_name2air_permeability, surface_name2airflow_exponent = (
        _allocate_air_leakage_init(air_leakage_records, surface_name2area)
    )

    # step 2 - reconcile shared surfaces for each dwelling pair
    _allocate_air_leakage_reconcile(
        surface_name2air_permeability,
        surface_name2airflow_exponent,
        surface_name_pair_groups,
    )

    # step 3 - reallocate remaining leakage over non-shared surfaces
    _allocate_air_leakage_reallocate(
        surface_name2air_permeability,
        air_leakage_records,
        surface_name2area,
        surface2other_surface_name,
    )

    # convert to air leakage and omit adiabatic and duplicate shared surfaces
    surface_name2allocation = {}

    for surface_name, air_permeability in surface_name2air_permeability.items():
        # omit adiabatic surfaces
        if surface_name in adiabatic_surface_names:
            continue

        # represent each shared boundary with one AirflowNetwork linkage
        if surface_name in surface2other_surface_name.values():
            continue

        surface_name2allocation[surface_name] = (
            air_permeability * surface_name2area[surface_name],
            surface_name2airflow_exponent[surface_name],
        )

    return surface_name2allocation


def _add_afn_simulation_control(idf: IDF) -> None:
    """Add the AirflowNetwork simulation control."""
    aark.ep.obj.add(
        idf,
        "AirflowNetwork:SimulationControl",
        Name=_uid("simulation_control"),
        AirflowNetwork_Control="MultizoneWithoutDistribution",
        Wind_Pressure_Coefficient_Type="Input",
        Height_Selection_for_Local_Wind_Pressure_Calculation="ExternalNode",
        Height_Dependence_of_External_Node_Temperature="No",
    )


def _add_afn_zones(
    idf: IDF,
    allocated_surface_names: Sequence[str],
    internal_door_names: Sequence[str],
    ambient_door_names: Sequence[str],
) -> None:
    """Add the zones participating in the final linkage graph."""
    for surface_name in allocated_surface_names:
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", surface_name
        )

        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Zone",
            Zone_Name=aark.ep.obj.get_zone(surface_obj).Name,
        )

        if aark.ep.field.equal("Surface", surface_obj, "Outside_Boundary_Condition"):
            aark.ep.obj.add(
                idf,
                "AirflowNetwork:MultiZone:Zone",
                Zone_Name=aark.ep.obj.get_other_zone(surface_obj).Name,
            )

    for door_name in internal_door_names:
        door_obj = aark.ep.obj.get_named(idf, "FenestrationSurface:Detailed", door_name)

        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Zone",
            Zone_Name=aark.ep.obj.get_zone(door_obj).Name,
        )
        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Zone",
            Zone_Name=aark.ep.obj.get_other_zone(door_obj).Name,
        )

    for door_name in ambient_door_names:
        door_obj = aark.ep.obj.get_named(idf, "FenestrationSurface:Detailed", door_name)

        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Zone",
            Zone_Name=aark.ep.obj.get_zone(door_obj).Name,
        )


def _add_afn_surfaces(
    idf: IDF,
    allocated_surface_names: Sequence[str],
    internal_door_names: Sequence[str],
    ambient_door_names: Sequence[str],
) -> None:
    """Add the AirflowNetwork surface linkages."""
    for surface_name in allocated_surface_names:
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", surface_name
        )
        external_node_uid = (
            _uid("external_node", surface_obj.Name)
            if aark.ep.field.equal(
                "Outdoors", surface_obj, "Outside_Boundary_Condition"
            )
            else ""
        )

        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Surface",
            Surface_Name=surface_name,
            Leakage_Component_Name=_uid("crack", surface_name),
            External_Node_Name=external_node_uid,
            WindowDoor_Opening_Factor_or_Crack_Factor="1",
        )

    for door_name in internal_door_names:
        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Surface",
            Surface_Name=door_name,
            Leakage_Component_Name=_uid("internal_door_opening"),
            WindowDoor_Opening_Factor_or_Crack_Factor="1",
            Ventilation_Control_Mode="NoVent",
        )

    for door_name in ambient_door_names:
        door_obj = aark.ep.obj.get_named(idf, "FenestrationSurface:Detailed", door_name)
        parent_surface_obj = aark.ep.obj.get_parent(door_obj)

        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Surface",
            Surface_Name=door_name,
            Leakage_Component_Name=_uid("ambient_door_opening"),
            External_Node_Name=_uid("external_node", parent_surface_obj.Name),
            WindowDoor_Opening_Factor_or_Crack_Factor="1",
            Ventilation_Control_Mode="NoVent",
        )


def _add_afn_ref_crack_condition(idf: IDF) -> None:
    """Add the reference conditions used by every fabric crack."""
    aark.ep.obj.add(
        idf,
        "AirflowNetwork:MultiZone:ReferenceCrackConditions",
        Name=_uid("ref_crack_condition"),
        Reference_Temperature=str(REF_TEMPERATURE),
        Reference_Barometric_Pressure=str(REF_PRESSURE),
        Reference_Humidity_Ratio=str(REF_HUMIDITY_RATIO),
    )


def _add_afn_cracks(
    idf: IDF, surface_name2allocation: Mapping[str, tuple[float, float]]
) -> None:
    """Add one test-derived crack component per represented fabric surface."""
    for surface_name, (leakage, exponent) in surface_name2allocation.items():
        coeff = REF_AIR_DENSITY * leakage / (3600 * 50**exponent)

        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Surface:Crack",
            Name=_uid("crack", surface_name),
            Air_Mass_Flow_Coefficient_at_Reference_Conditions=str(coeff),
            Air_Mass_Flow_Exponent=str(exponent),
            Reference_Crack_Conditions=_uid("ref_crack_condition"),
        )


def _add_afn_opening(
    idf: IDF,
    internal_door_names: Sequence[str],
    ambient_door_names: Sequence[str],
    door_airflow_params: Mapping[str, str],
) -> None:
    """Add the shared closed-door detailed-opening components."""
    shared_obj_fields = {
        "Type_of_Rectangular_Large_Vertical_Opening_LVO": "NonPivoted",
        "Extra_Crack_Length_or_Height_of_Pivoting_Axis": "0",
        "Number_of_Sets_of_Opening_Factor_Data": "2",
        "Opening_Factor_1": "0",
        "Discharge_Coefficient_for_Opening_Factor_1": door_airflow_params[
            "closed_discharge_coeff"
        ],
        "Width_Factor_for_Opening_Factor_1": "0",
        "Height_Factor_for_Opening_Factor_1": "0",
        "Start_Height_Factor_for_Opening_Factor_1": "0",
        "Opening_Factor_2": "1",
        "Discharge_Coefficient_for_Opening_Factor_2": door_airflow_params[
            "open_discharge_coeff"
        ],
        "Width_Factor_for_Opening_Factor_2": "1",
        "Height_Factor_for_Opening_Factor_2": "1",
        "Start_Height_Factor_for_Opening_Factor_2": "0",
    }

    if internal_door_names:
        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Component:DetailedOpening",
            Name=_uid("internal_door_opening"),
            Air_Mass_Flow_Coefficient_When_Opening_is_Closed=door_airflow_params[
                "internal_closed_mass_flow_coeff"
            ],
            Air_Mass_Flow_Exponent_When_Opening_is_Closed=door_airflow_params[
                "internal_closed_mass_flow_exponent"
            ],
            **shared_obj_fields,
        )

    if ambient_door_names:
        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:Component:DetailedOpening",
            Name=_uid("ambient_door_opening"),
            Air_Mass_Flow_Coefficient_When_Opening_is_Closed=door_airflow_params[
                "ambient_closed_mass_flow_coeff"
            ],
            Air_Mass_Flow_Exponent_When_Opening_is_Closed=door_airflow_params[
                "ambient_closed_mass_flow_exponent"
            ],
            **shared_obj_fields,
        )


def _add_afn_external_nodes(
    idf: IDF,
    wind_pressure_coeff_records: Sequence[AirflowRecord],
    allocated_surface_names: Sequence[str],
    ambient_door_names: Sequence[str],
) -> None:
    """Add one external node for each represented outdoor surface."""
    afn_external_surface_names = set()

    for surface_name in allocated_surface_names:
        surface_obj = aark.ep.obj.get_named(
            idf, "BuildingSurface:Detailed", surface_name
        )
        if aark.ep.field.equal("Outdoors", surface_obj, "Outside_Boundary_Condition"):
            afn_external_surface_names.add(surface_obj.Name)

    for door_name in ambient_door_names:
        door_obj = aark.ep.obj.get_named(idf, "FenestrationSurface:Detailed", door_name)
        afn_external_surface_names.add(aark.ep.obj.get_parent(door_obj).Name)

    for wind_pressure_coeff_record in wind_pressure_coeff_records:
        record_name = str(wind_pressure_coeff_record["name"])
        ref_height = float(str(wind_pressure_coeff_record["ref_height"]))
        external_surface_names = wind_pressure_coeff_record["external_surfaces"]

        for surface_name in external_surface_names:
            if surface_name not in afn_external_surface_names:
                continue

            aark.ep.obj.add(
                idf,
                "AirflowNetwork:MultiZone:ExternalNode",
                Name=_uid("external_node", surface_name),
                External_Node_Height=str(ref_height),
                Wind_Pressure_Coefficient_Curve_Name=record_name,
                Symmetric_Wind_Pressure_Coefficient_Curve="Yes",
                Wind_Angle_Type="Relative",
            )


def _add_afn_wind_pressure_coeffs(
    idf: IDF, wind_pressure_coeff_records: Sequence[AirflowRecord]
) -> None:
    """Add the wind-angle array and grouped wind pressure coefficient records."""
    angles_obj_name = _uid("wind_pressure_coeff_angles")

    angles = wind_pressure_coeff_records[0]["angles"]
    obj_fields = {
        f"Wind_Direction_{i}": angle for i, angle in enumerate(angles, start=1)
    }
    aark.ep.obj.add(
        idf,
        "AirflowNetwork:MultiZone:WindPressureCoefficientArray",
        Name=angles_obj_name,
        **obj_fields,
    )

    for wind_pressure_coeff_record in wind_pressure_coeff_records:
        record_name = str(wind_pressure_coeff_record["name"])
        coeffs = wind_pressure_coeff_record["coeffs"]

        obj_fields = {
            f"Wind_Pressure_Coefficient_Value_{i}": val
            for i, val in enumerate(coeffs, start=1)
        }
        aark.ep.obj.add(
            idf,
            "AirflowNetwork:MultiZone:WindPressureCoefficientValues",
            Name=record_name,
            AirflowNetworkMultiZoneWindPressureCoefficientArray_Name=angles_obj_name,
            **obj_fields,
        )


def apply(
    idf: IDF,
    air_leakage_records: Sequence[AirflowRecord],
    wind_pressure_coeff_records: Sequence[AirflowRecord],
    door_airflow_params: Mapping[str, str],
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

    `door_airflow_params` contains the door-opening parameters. The ambient keys are
    required only when an `air_leakage_record` supplies `ambient_doors`.

    ```python
    door_airflow_params = {
        "internal_closed_mass_flow_coeff": "0.002",  # kg s-1 m-1 @ 1 Pa
        "internal_closed_mass_flow_exponent": "0.6",
        "closed_discharge_coeff": "1e-7",
        "open_discharge_coeff": "0.69",
        "ambient_closed_mass_flow_coeff": "3.25e-4",  # kg s-1 m-1 @ 1 Pa
        "ambient_closed_mass_flow_exponent": "0.6",
    }
    ```
    """
    # validate aark requirements
    aark.ep._pact.validate_ep_ver(idf)
    aark.ep._pact.validate_no_space(idf)
    aark.ep._pact.validate_no_afn_objs(idf)

    # validate user inputs
    _validate_air_leakage_records(air_leakage_records, idf)

    all_internal_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "internal_doors"
    )
    all_ambient_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "ambient_doors"
    )

    _validate_wind_pressure_coeff_records(
        wind_pressure_coeff_records, idf, air_leakage_records
    )
    _validate_door_airflow_params(door_airflow_params, all_ambient_door_names)

    # allocate leakage parameters
    surface_name2allocation = _allocate_air_leakage(air_leakage_records, idf)
    allocated_surface_names = tuple(surface_name2allocation)

    # add afn objects
    _add_afn_simulation_control(idf)
    _add_afn_zones(
        idf, allocated_surface_names, all_internal_door_names, all_ambient_door_names
    )
    _add_afn_surfaces(
        idf, allocated_surface_names, all_internal_door_names, all_ambient_door_names
    )
    _add_afn_ref_crack_condition(idf)
    _add_afn_cracks(idf, surface_name2allocation)
    _add_afn_opening(
        idf, all_internal_door_names, all_ambient_door_names, door_airflow_params
    )
    _add_afn_external_nodes(
        idf,
        wind_pressure_coeff_records,
        allocated_surface_names,
        all_ambient_door_names,
    )
    _add_afn_wind_pressure_coeffs(idf, wind_pressure_coeff_records)


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

    all_allocation_surface_names = _get_all_vals_by_record_key(
        air_leakage_records, "allocation_surfaces"
    )
    all_internal_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "internal_doors"
    )
    all_ambient_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "ambient_doors"
    )

    # allocation surface names must be unique and identify detailed building surfaces
    aark.ep.obj.validate_obj_names(
        idf, "BuildingSurface:Detailed", *all_allocation_surface_names
    )

    # internal door names must be unique and identify fenestration surfaces
    aark.ep.obj.validate_obj_names(
        idf, "FenestrationSurface:Detailed", *all_internal_door_names
    )

    # only one side of each internal door must be supplied
    aark.ep.obj.validate_no_other_surface(
        idf, "FenestrationSurface:Detailed", *all_internal_door_names
    )

    # ambient door names must be unique and identify fenestration surfaces
    aark.ep.obj.validate_obj_names(
        idf, "FenestrationSurface:Detailed", *all_ambient_door_names
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

    all_record_names = _get_all_vals_by_record_key(wind_pressure_coeff_records, "name")
    all_external_surface_names = _get_all_vals_by_record_key(
        wind_pressure_coeff_records, "external_surfaces"
    )

    unique_record_names = set(all_record_names)
    normalised_record_names = {
        record_name.strip().upper() for record_name in unique_record_names
    }

    # record names must be unique
    if len(all_record_names) != len(unique_record_names):
        raise ValueError(
            f"Duplicate names in wind pressure coefficient records: {all_record_names}."
        )

    # unique record names must not be equivalent
    if len(unique_record_names) != len(normalised_record_names):
        raise ValueError(
            f"Equivalent names in wind pressure coefficient records: {all_record_names}."
        )

    # external surface names must be unique and identify detailed building surfaces
    aark.ep.obj.validate_obj_names(
        idf, "BuildingSurface:Detailed", *all_external_surface_names
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
    all_allocation_surface_names = _get_all_vals_by_record_key(
        air_leakage_records, "allocation_surfaces"
    )
    all_ambient_door_names = _get_all_vals_by_record_key(
        air_leakage_records, "ambient_doors"
    )

    all_external_allocation_surface_names = {
        surface_name
        for surface_name in all_allocation_surface_names
        if aark.ep.field.equal(
            "Outdoors",
            aark.ep.obj.get_named(idf, "BuildingSurface:Detailed", surface_name),
            "Outside_Boundary_Condition",
        )
    }
    all_ambient_surface_names = {
        aark.ep.obj.get_named(
            idf, "FenestrationSurface:Detailed", door_name
        ).Building_Surface_Name
        for door_name in all_ambient_door_names
    }

    missing_surface_names = (
        all_external_allocation_surface_names | all_ambient_surface_names
    ) - set(all_external_surface_names)
    if missing_surface_names:
        raise ValueError(
            f"Missing wind pressure coefficients for outdoor surfaces: {missing_surface_names}."
        )


def _validate_door_airflow_params(
    door_airflow_params: Mapping[str, str], ambient_door_names: Sequence[str]
) -> None:
    """Validate door airflow parameter keys for the supplied door types."""
    required_keys = {
        "internal_closed_mass_flow_coeff",
        "internal_closed_mass_flow_exponent",
        "closed_discharge_coeff",
        "open_discharge_coeff",
    }
    optional_keys = {
        "ambient_closed_mass_flow_coeff",
        "ambient_closed_mass_flow_exponent",
    }
    valid_keys = required_keys | optional_keys

    # the mapping must contain all required keys and only allowed keys
    if not required_keys <= set(door_airflow_params) <= valid_keys:
        raise ValueError(
            f"Invalid door airflow parameter keys: {door_airflow_params.keys()}."
        )

    # ambient values must be supplied when ambient doors are supplied
    if ambient_door_names:
        missing_ambient_keys = optional_keys - door_airflow_params.keys()
        if missing_ambient_keys:
            raise ValueError(
                f"Missing ambient door airflow parameter keys: {missing_ambient_keys}."
            )
