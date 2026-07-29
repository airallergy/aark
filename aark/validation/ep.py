"""Validate `aark` assumptions about EnergyPlus model configurations.

For simplicity, `aark` assumes the EnergyPlus model is configured in certain ways. The
validators in this module check those assumptions, and standardise relevant inputs.
"""

from typing import TYPE_CHECKING

import numpy as np

import aark.ep.generic

if TYPE_CHECKING:
    from eppy.modeleditor import IDF


def validate_no_building_rel_north(idf: IDF) -> None:
    """Validate that the building's north axis is zero or unused."""
    (building_obj,) = idf.idfobjects["BUILDING"]
    rel_north = aark.ep.generic.get_field_val_as_float(building_obj, "North_Axis")

    if not np.isclose(rel_north, 0):
        raise ValueError(f"Building.North_Axis is not zero: {building_obj}.")

    building_obj.North_Axis = ""


def validate_no_zone_rel_north(idf: IDF) -> None:
    """Validate that every zone's direction of relative north is zero or unused."""
    for zone_obj in idf.idfobjects["ZONE"]:
        rel_north = aark.ep.generic.get_field_val_as_float(
            zone_obj, "Direction_of_Relative_North"
        )
        if not np.isclose(rel_north, 0):
            raise ValueError(
                f"Zone.Direction_of_Relative_North is not zero: {zone_obj}."
            )

        zone_obj.Direction_of_Relative_North = ""
