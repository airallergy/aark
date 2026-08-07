"""Generic EnergyPlus functions."""

from typing import TYPE_CHECKING

import aark.ep.field

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF


MAX_EP_STR_FIELD_LEN = 100


def add_named_obj(
    idf: IDF, cls_name: str, obj_name: str, **other_obj_fields: str
) -> None:
    """Add a named object if an identical object does not exist."""
    if not obj_name:
        raise ValueError(f"Empty object name: {obj_name}.")

    if len(obj_name) > MAX_EP_STR_FIELD_LEN:
        raise ValueError(
            f"EnergyPlus object name exceeds {MAX_EP_STR_FIELD_LEN} characters: {obj_name}."
        )

    if not named_obj_exists(idf, cls_name, obj_name, **other_obj_fields):
        idf.newidfobject(
            cls_name, defaultvalues=False, Name=obj_name, **other_obj_fields
        )


def add_unnamed_obj(idf: IDF, cls_name: str, **obj_fields: str) -> None:
    """Add an unnamed object if an identical object does not exist."""
    if not unnamed_obj_exists(idf, cls_name, **obj_fields):
        idf.newidfobject(cls_name, defaultvalues=False, **obj_fields)


def add_obj(idf: IDF, cls_name: str, **obj_fields: str) -> None:
    """Add an object if an identical object does not exist."""
    match obj_fields:
        case {"Name": obj_name, **other_obj_fields}:
            add_named_obj(idf, cls_name, obj_name, **other_obj_fields)
        case _:
            add_unnamed_obj(idf, cls_name, **obj_fields)


def get_named_object(idf: IDF, cls_name: str, obj_name: str) -> EpBunch:
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


def get_parent_obj(obj: EpBunch) -> EpBunch:
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

    return get_named_object(obj.theidf, parent_cls_name, parent_obj_name)


def get_zone_obj(obj: EpBunch) -> EpBunch:
    """Get the zone object of an object."""
    match obj.key.upper():
        case "BUILDINGSURFACE:DETAILED":
            return get_parent_obj(obj)
        case "FENESTRATIONSURFACE:DETAILED":
            surface_obj = get_parent_obj(obj)
            return get_parent_obj(surface_obj)
        case _:
            raise ValueError(f"Unsupported class: {obj.key}.")


def rstrip_obj(obj: EpBunch) -> None:
    """Remove trailing empty fields of an object."""
    # remove leading/trailing whitespace from string field values
    obj.fieldvalues[:] = [
        val.strip() if isinstance(val, str) else val for val in obj.fieldvalues
    ]  # obj.fieldvalues cannot be reassigned directly

    if all(val == "" for val in obj.fieldvalues[1:]):
        raise ValueError(f"Object is empty: {obj}.")

    # remove trailing empty fields
    while obj.fieldvalues[-1] == "":
        obj.fieldvalues.pop()


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def has_named_obj(idf: IDF, cls_name: str, obj_name: str) -> bool:
    """Return whether an object class contains a named object."""
    return any(
        aark.ep.field.equal(obj_name, obj, "Name") for obj in idf.idfobjects[cls_name]
    )


def named_obj_exists(
    idf: IDF, cls_name: str, obj_name: str, **other_obj_fields: str
) -> bool:
    """Return whether an identical named object exists."""
    if not has_named_obj(idf, cls_name, obj_name):
        return False

    existing_obj = get_named_object(idf, cls_name, obj_name)

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


def unnamed_obj_exists(idf: IDF, cls_name: str, **obj_fields: str) -> bool:
    """Return whether an identical unnamed object exists."""
    tmp_idf = type(idf)()
    tmp_idf.new()
    tmp_obj = tmp_idf.newidfobject(cls_name, defaultvalues=False, **obj_fields)

    return any(
        obj.fieldvalues[1:] == tmp_obj.fieldvalues[1:]
        for obj in idf.idfobjects[cls_name]
    )
