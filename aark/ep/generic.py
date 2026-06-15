"""Generic EnergyPlus functions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from eppy.bunch_subclass import EpBunch

    type Float64Array2D = np.ndarray[tuple[int, int], np.dtype[np.float64]]


def get_zone_name(obj: EpBunch) -> str:
    """Get the zone name for a child object."""
    class_name = obj.key.upper()

    match class_name:
        case "BUILDINGSURFACE:DETAILED":
            return obj.Zone_Name
        case "FENESTRATIONSURFACE:DETAILED":
            surface = obj.theidf.getobject(
                "BUILDINGSURFACE:DETAILED", obj.Building_Surface_Name
            )
            return surface.Zone_Name
        case _:
            raise ValueError(f"Unsupported class: {class_name}.")


def get_field_default_value(obj: EpBunch, field_name: str) -> str:
    """Get the default value of a field."""
    values = obj.getfieldidd_item(field_name, "default")

    if not values:
        raise ValueError(f"No default value: {obj.key}.{field_name}.")

    (value,) = values
    return value


def get_field_value_as_float(obj: EpBunch, field_name: str) -> float:
    """Get a real field value as float."""
    # sanity check
    if obj.getfieldidd_item(field_name, "type") != ["real"]:
        raise ValueError(f"Field is not a real number: {obj.key}.{field_name}.")

    # get the field value
    value = getattr(obj, field_name)

    # set default value if the field is empty
    if value == "":
        value = get_field_default_value(obj, field_name)

    # convert to float
    return float(value)


def rstrip_empty_fields(obj: EpBunch) -> None:
    """Remove trailing empty fields of an object."""
    # Remove leading/trailing whitespace from string field values
    obj.fieldvalues[:] = [
        item.strip() if isinstance(item, str) else item for item in obj.fieldvalues
    ]  # obj.fieldvalues cannot be reassigned directly

    if all(v == "" for v in obj.fieldvalues[1:]):
        raise ValueError(f"Object is empty: {obj}.")

    # Remove trailing empty fields
    while obj.fieldvalues[-1] == "":
        obj.fieldvalues.pop()
