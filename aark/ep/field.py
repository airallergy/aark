"""Manipulate EnergyPlus object fields."""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch

    type EppyVal = str | float | int


AUTO_NUMERIC_VALS = frozenset({"AUTOSIZE", "AUTOCALCULATE"})


def get_type(obj: EpBunch, name: str) -> str:
    """Get a field's type."""
    field_idx = obj.fieldnames.index(name)
    obj_idx = obj.theidf.model.dtls.index(obj.key.upper())
    idd_name = obj.theidf.block[obj_idx][field_idx]
    field_types = obj.getfieldidd_item(name, "type")

    if field_types in (["real"], ["integer"]) or idd_name.startswith("N"):
        return "numeric"
    elif idd_name.startswith("A"):
        return "alpha"
    else:
        raise ValueError(f"Unknown field type: {obj.key}.{name}.")


def normalise(val: EppyVal, obj: EpBunch, name: str) -> str:
    """Normalise a field value for comparison."""
    text = str(val).strip()
    if obj.get_retaincase(name):
        return text
    else:
        return text.upper()


def get_default(obj: EpBunch, name: str) -> str:
    """Get the default value of a field."""
    vals = obj.getfieldidd_item(name, "default")

    if not vals:
        raise ValueError(f"Field has no default: {obj.key}.{name}.")

    (val,) = vals
    return str(val)


def default_if_empty(val: EppyVal, obj: EpBunch, name: str) -> str:
    """Return the field default for an empty value when available."""
    if (
        isinstance(val, str)
        and val.strip() == ""
        and obj.getfieldidd_item(name, "default")
    ):
        val = get_default(obj, name)

    return str(val)


def as_float(obj: EpBunch, name: str) -> float:
    """Get a numeric field value as float.

    Its default value is used when empty.
    """
    if not _is_numeric(obj, name):
        raise ValueError(f"Field is not numeric: {obj.key}.{name}.")

    val = obj[name]

    if isinstance(val, str):
        val = val.strip()

    if val == "":
        val = get_default(obj, name)

    return float(val)


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def _is_numeric(obj: EpBunch, name: str) -> bool:
    """Return whether a field has an EnergyPlus numeric type."""
    return get_type(obj, name) == "numeric"


def _numeric_equal(left: str, right: str) -> bool:
    """Return whether two numeric values are equal."""
    if (
        (left == "")
        or (right == "")
        or (left in AUTO_NUMERIC_VALS)
        or (right in AUTO_NUMERIC_VALS)
    ):
        return left == right
    else:
        return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)


def _alpha_equal(left: str, right: str) -> bool:
    """Return whether two alpha values are equal."""
    return left == right


def _equal(left: EppyVal, right: EppyVal, obj: EpBunch, name: str) -> bool:
    """Return whether two values are equal for a given field."""
    left = normalise(left, obj, name)
    right = normalise(right, obj, name)

    if _is_numeric(obj, name):
        return _numeric_equal(left, right)
    else:
        return _alpha_equal(left, right)


def equal(left: EppyVal, obj: EpBunch, name: str) -> bool:
    """Return whether a given value equals a field value."""
    return _equal(left, obj[name], obj, name)


def equiv(left: EppyVal, obj: EpBunch, name: str) -> bool:
    """Return whether a given value equals a field value after applying defaults."""
    return _equal(
        default_if_empty(left, obj, name),
        default_if_empty(obj[name], obj, name),
        obj,
        name,
    )


def startswith(obj: EpBunch, name: str, prefix: str) -> bool:
    """Return whether an alpha field starts with a prefix."""
    if _is_numeric(obj, name):
        raise ValueError(f"Field is numeric: {obj.key}.{name}.")

    field_val = normalise(obj[name], obj, name)
    prefix = normalise(prefix, obj, name)
    return field_val.startswith(prefix)
