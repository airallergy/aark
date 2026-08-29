"""Validate `aark` assumptions about EnergyPlus model configurations.

For simplicity, `aark` assumes the EnergyPlus model is configured in certain ways. The
validators in this module check those assumptions, and standardise relevant inputs.
"""

from typing import TYPE_CHECKING

import aark.ep.field

if TYPE_CHECKING:
    from eppy.modeleditor import IDF


MIN_EP_VER = (24, 1)


def validate_ep_ver(idf: IDF) -> None:
    """Validate the EnergyPlus version of the model."""

    def ep_ver_as_str(ver: tuple[int, int]) -> str:
        major, minor = ver
        return f"{major}.{minor}"

    # the idd version must meet the minimum
    idd_ver_major, idd_ver_minor, *_ = map(int, idf.idd_version)
    idd_ver = (idd_ver_major, idd_ver_minor)

    if idd_ver < MIN_EP_VER:
        raise ValueError(
            f"IDD version is not {ep_ver_as_str(MIN_EP_VER)} or later: {ep_ver_as_str(idd_ver)}."
        )

    # the idf version must meet the minimum
    (ver_obj,) = idf.idfobjects["Version"]
    idf_ver_str = str(ver_obj.Version_Identifier).strip()
    idf_ver_major, idf_ver_minor, *_ = map(int, idf_ver_str.split("."))
    idf_ver = (idf_ver_major, idf_ver_minor)

    if idf_ver < MIN_EP_VER:
        raise ValueError(
            f"IDF version is not {ep_ver_as_str(MIN_EP_VER)} or later: {ep_ver_as_str(idf_ver)}."
        )

    # the idd and idf versions must match
    if idf_ver != idd_ver:
        raise ValueError(
            f"IDD and IDF versions do not match: IDD={ep_ver_as_str(idd_ver)}, IDF={ep_ver_as_str(idf_ver)}."
        )


def validate_no_building_rel_north(idf: IDF) -> None:
    """Validate that the building's north axis is zero or unused."""
    (building_obj,) = idf.idfobjects["Building"]
    if not aark.ep.field.equiv(0, building_obj, "North_Axis"):
        raise ValueError(f"`Building.North_Axis` is not zero: {building_obj}.")

    building_obj.North_Axis = ""


def validate_no_zone_rel_north(idf: IDF) -> None:
    """Validate that every zone's direction of relative north is zero or unused."""
    # NOTE: fast fail
    for zone_obj in idf.idfobjects["Zone"]:
        if not aark.ep.field.equiv(0, zone_obj, "Direction_of_Relative_North"):
            raise ValueError(
                f"`Zone.Direction_of_Relative_North` is not zero: {zone_obj}."
            )

        zone_obj.Direction_of_Relative_North = ""


def validate_no_space(idf: IDF) -> None:
    """Validate that the IDF does not use EnergyPlus `Space` objects."""
    space_objs = idf.idfobjects["Space"]

    if space_objs:
        raise ValueError(f"`Space` object is not supported: {space_objs}.")
