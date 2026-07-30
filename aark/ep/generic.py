"""Generic EnergyPlus functions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF


MAX_EP_STR_FIELD_LENGTH = 100


def add_named_obj(
    idf: IDF, cls_name: str, obj_name: str, **other_obj_fields: str
) -> None:
    """Add a named object if an identical object does not exist."""
    if not obj_name:
        raise ValueError(f"Empty object name: {obj_name}.")

    if len(obj_name) > MAX_EP_STR_FIELD_LENGTH:
        raise ValueError(
            f"EnergyPlus object name exceeds {MAX_EP_STR_FIELD_LENGTH} characters: {obj_name}."
        )

    if not named_obj_exists(idf, cls_name, obj_name, **other_obj_fields):
        idf.newidfobject(
            cls_name, defaultvalues=False, Name=obj_name, **other_obj_fields
        )


def add_unnamed_obj(idf: IDF, cls_name: str, **obj_fields: str) -> None:
    """Add an unnamed object if an identical object does not exist."""
    raise NotImplementedError


def add_obj(idf: IDF, cls_name: str, **obj_fields: str) -> None:
    """Add an object if an identical object does not exist."""
    match obj_fields:
        case {"Name": obj_name, **other_obj_fields}:
            add_named_obj(idf, cls_name, obj_name, **other_obj_fields)
        case _:
            add_unnamed_obj(idf, cls_name, **obj_fields)


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


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_zones_exist_by_name(idf: IDF, zone_names: Iterable[str]) -> None:
    """Validate that zones exist in the idf by zone name."""
    existing_zone_names = {str(obj.Name) for obj in idf.idfobjects["ZONE"]}
    missing_zone_names = sorted(set(zone_names) - existing_zone_names)
    if missing_zone_names:
        raise ValueError(f"Missing zones: {missing_zone_names}.")


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def named_obj_exists(
    idf: IDF, cls_name: str, obj_name: str, **other_obj_fields: str
) -> bool:
    """Check whether an identical named object exists."""
    existing_obj = idf.getobject(cls_name, obj_name)

    if existing_obj is None:
        return False

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
