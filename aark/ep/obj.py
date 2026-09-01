"""Manipulate EnergyPlus objects."""

from collections import Counter
from typing import TYPE_CHECKING

import aark.ep.field
from aark.ep.field import MAX_EP_STR_FIELD_LEN

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF


def _add_named(idf: IDF, cls_name: str, obj_name: str, **other_obj_fields: str) -> None:
    """Add a named object if an identical object does not exist."""
    if not obj_name:
        raise ValueError(f"Empty object name: {obj_name}.")

    if len(obj_name) > MAX_EP_STR_FIELD_LEN:
        raise ValueError(
            f"EnergyPlus object name exceeds {MAX_EP_STR_FIELD_LEN} characters: {obj_name}."
        )

    if not _named_exists(idf, cls_name, obj_name, **other_obj_fields):
        idf.newidfobject(
            cls_name, defaultvalues=False, Name=obj_name, **other_obj_fields
        )


def _add_unnamed(idf: IDF, cls_name: str, **obj_fields: str) -> None:
    """Add an unnamed object if an identical object does not exist."""
    if not _unnamed_exists(idf, cls_name, **obj_fields):
        idf.newidfobject(cls_name, defaultvalues=False, **obj_fields)


def add(idf: IDF, cls_name: str, **obj_fields: str) -> None:
    """Add an object if an identical object does not exist."""
    match obj_fields:
        case {"Name": obj_name, **other_obj_fields}:
            _add_named(idf, cls_name, obj_name, **other_obj_fields)
        case _:
            _add_unnamed(idf, cls_name, **obj_fields)


def get_named(idf: IDF, cls_name: str, obj_name: str) -> EpBunch:
    """Get a uniquely named object, raising if it is missing or duplicated."""
    objs = [
        obj
        for obj in idf.idfobjects[cls_name]
        if aark.ep.field.equal(obj_name, obj, "Name")
    ]

    if not objs:
        raise ValueError(f"Missing {cls_name} object: {obj_name}.")

    if len(objs) > 1:
        raise ValueError(f"Duplicate {cls_name} object name: {obj_name}.")

    return objs[0]


def get_parent(obj: EpBunch) -> EpBunch:
    """Get the parent object of an object."""
    match obj.key.upper():
        case "BUILDINGSURFACE:DETAILED":
            parent_obj_name = obj.Zone_Name
            parent_cls_name = "Zone"
        case "FENESTRATIONSURFACE:DETAILED":
            parent_obj_name = obj.Building_Surface_Name
            parent_cls_name = "BuildingSurface:Detailed"
        case _:
            raise ValueError(f"Unsupported class: {obj.key}.")

    return get_named(obj.theidf, parent_cls_name, parent_obj_name)


def get_zone(obj: EpBunch) -> EpBunch:
    """Get the zone object of an object."""
    match obj.key.upper():
        case "BUILDINGSURFACE:DETAILED":
            return get_parent(obj)
        case "FENESTRATIONSURFACE:DETAILED":
            surface_obj = get_parent(obj)
            return get_parent(surface_obj)
        case _:
            raise ValueError(f"Unsupported class: {obj.key}.")


def get_other_zone(obj: EpBunch) -> EpBunch:
    """Get the other zone object of an object."""
    match obj.key.upper():
        case "BUILDINGSURFACE:DETAILED":
            surface_obj = obj
        case "FENESTRATIONSURFACE:DETAILED":
            surface_obj = get_parent(obj)
        case _:
            raise ValueError(f"Unsupported class: {obj.key}.")

    if not aark.ep.field.equal("Surface", surface_obj, "Outside_Boundary_Condition"):
        raise ValueError(
            f"Invalid or unsupported outside boundary condition: {surface_obj.Outside_Boundary_Condition}."
        )

    other_surface_obj = get_named(
        surface_obj.theidf,
        "BuildingSurface:Detailed",
        surface_obj.Outside_Boundary_Condition_Object,
    )
    return get_parent(other_surface_obj)


def rstrip(obj: EpBunch) -> None:
    """Remove trailing empty fields of an object."""
    # remove leading/trailing whitespace from string field values
    obj.fieldvalues[:] = [
        val.strip() if isinstance(val, str) else val for val in obj.fieldvalues
    ]  # `obj.fieldvalues` cannot be reassigned directly

    if all(val == "" for val in obj.fieldvalues[1:]):
        raise ValueError(f"Object is empty: {obj}.")

    # remove trailing empty fields
    while obj.fieldvalues[-1] == "":
        obj.fieldvalues.pop()


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_obj_names(idf: IDF, cls_name: str, *obj_names: str) -> None:
    """Validate that object names are unique and identify objects in the IDF."""
    # object names must be unique
    duplicate_names = sorted(name for name, n in Counter(obj_names).items() if n > 1)
    if duplicate_names:
        raise ValueError(f"Duplicate {cls_name} object names: {duplicate_names}.")

    # NOTE: fast fail
    for obj_name in obj_names:
        # object names must identify objects in the idf
        get_named(idf, cls_name, obj_name)


def validate_no_other_surface(idf: IDF, cls_name: str, *surface_names: str) -> None:
    """Validate that no interzonal surface pair has both sides present."""
    # supplied surface names must identify objects of the specified class
    surface_objs = [
        get_named(idf, cls_name, surface_name) for surface_name in surface_names
    ]

    # other surface names must identify objects of the specified class
    other_surface_objs = [
        get_named(idf, cls_name, surface_obj.Outside_Boundary_Condition_Object)
        for surface_obj in surface_objs
    ]

    # no interzonal surface pair may have both sides present
    normalised_surface_names = {
        aark.ep.field.normalise(surface_obj.Name, surface_obj, "Name")
        for surface_obj in surface_objs
    }
    normalised_other_surface_names = {
        aark.ep.field.normalise(other_surface_obj.Name, other_surface_obj, "Name")
        for other_surface_obj in other_surface_objs
    }

    if normalised_surface_names & normalised_other_surface_names:
        raise ValueError(
            f"Found both sides of interzonal {cls_name} pairs: {surface_names}."
        )


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def has_named(idf: IDF, cls_name: str, obj_name: str) -> bool:
    """Return whether an object class contains a named object."""
    return any(
        aark.ep.field.equal(obj_name, obj, "Name") for obj in idf.idfobjects[cls_name]
    )


def _named_exists(
    idf: IDF, cls_name: str, obj_name: str, **other_obj_fields: str
) -> bool:
    """Return whether an identical named object exists."""
    if not has_named(idf, cls_name, obj_name):
        return False

    existing_obj = get_named(idf, cls_name, obj_name)

    tmp_idf = type(idf)()
    tmp_idf.new()
    tmp_obj = tmp_idf.newidfobject(
        cls_name, defaultvalues=False, Name=obj_name, **other_obj_fields
    )

    if existing_obj.fieldvalues[2:] != tmp_obj.fieldvalues[2:]:
        raise ValueError(
            f"Object exists with the same name but different field values: {obj_name}."
        )

    return True


def _unnamed_exists(idf: IDF, cls_name: str, **obj_fields: str) -> bool:
    """Return whether an identical unnamed object exists."""
    tmp_idf = type(idf)()
    tmp_idf.new()
    tmp_obj = tmp_idf.newidfobject(cls_name, defaultvalues=False, **obj_fields)

    return any(
        obj.fieldvalues[1:] == tmp_obj.fieldvalues[1:]
        for obj in idf.idfobjects[cls_name]
    )


def exists(idf: IDF, cls_name: str, **obj_fields: str) -> bool:
    """Return whether an identical object exists."""
    match obj_fields:
        case {"Name": obj_name, **other_obj_fields}:
            return _named_exists(idf, cls_name, obj_name, **other_obj_fields)
        case _:
            return _unnamed_exists(idf, cls_name, **obj_fields)
