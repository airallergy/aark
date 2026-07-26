"""Generic EnergyPlus functions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch


def get_parent_obj(obj: EpBunch) -> EpBunch:
    """Get the parent object of an object."""
    match obj.key.upper():
        case "BUILDINGSURFACE:DETAILED":
            parent_name = obj.Zone_Name
            parent_cls = "ZONE"
        case "FENESTRATIONSURFACE:DETAILED":
            parent_name = obj.Building_Surface_Name
            parent_cls = "BUILDINGSURFACE:DETAILED"
        case _ as cls_name:
            raise ValueError(f"Unsupported class: {cls_name}.")

    parent_obj = obj.theidf.getobject(parent_cls, parent_name)

    if parent_obj is None:
        raise ValueError(f"Missing {parent_cls} object: {parent_name}.")

    return parent_obj


def get_zone_obj(obj: EpBunch) -> EpBunch:
    """Get the zone object of an object."""
    match obj.key.upper():
        case "BUILDINGSURFACE:DETAILED":
            return get_parent_obj(obj)
        case "FENESTRATIONSURFACE:DETAILED":
            surface_obj = get_parent_obj(obj)
            return get_parent_obj(surface_obj)
        case _ as cls_name:
            raise ValueError(f"Unsupported class: {cls_name}.")


def get_field_default_val(obj: EpBunch, field_name: str) -> str | float | int:
    """Get the default value of a field."""
    vals = obj.getfieldidd_item(field_name, "default")

    if not vals:
        raise ValueError(f"No default value: {obj.key}.{field_name}.")

    (val,) = vals
    assert isinstance(val, (str, float, int))  # eppy typing
    return val


def get_field_val_as_float(obj: EpBunch, field_name: str) -> float:
    """Get a real field value as float."""
    # sanity check
    if obj.getfieldidd_item(field_name, "type") != ["real"]:
        raise ValueError(f"Field is not a real number: {obj.key}.{field_name}.")

    # get the field value
    val = getattr(obj, field_name)

    # set default value if the field is empty
    if val == "":
        val = get_field_default_val(obj, field_name)

    # convert to float
    return float(val)


def rstrip_empty_fields(obj: EpBunch) -> None:
    """Remove trailing empty fields of an object."""
    # Remove leading/trailing whitespace from string field values
    obj.fieldvalues[:] = [
        item.strip() if isinstance(item, str) else item for item in obj.fieldvalues
    ]  # obj.fieldvalues cannot be reassigned directly

    if all(val == "" for val in obj.fieldvalues[1:]):
        raise ValueError(f"Object is empty: {obj}.")

    # Remove trailing empty fields
    while obj.fieldvalues[-1] == "":
        obj.fieldvalues.pop()
