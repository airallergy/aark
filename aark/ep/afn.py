"""Manipulate EnergyPlus AirflowNetwork objects."""

from typing import TYPE_CHECKING

import aark.ep.field
import aark.ep.obj

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF

OPENING_COMPONENT_CLS_NAMES = frozenset(
    {
        "AirflowNetwork:MultiZone:Component:DetailedOpening",
        "AirflowNetwork:MultiZone:Component:HorizontalOpening",
        "AirflowNetwork:MultiZone:Component:SimpleOpening",
    }
)


def get_surface_obj(idf: IDF, surface_name: str) -> EpBunch:
    """Get a unique Airflow Network surface object linked to a surface."""
    objs = [
        obj
        for obj in idf.idfobjects["AirflowNetwork:MultiZone:Surface"]
        if aark.ep.field.equal(surface_name, obj, "Surface_Name")
    ]

    if not objs:
        raise ValueError(f"Missing Airflow Network surface object: {surface_name}.")

    if len(objs) > 1:
        raise ValueError(f"Duplicate Airflow Network surface objects: {surface_name}.")

    return objs[0]


# -----------------------------------------------------------------------------
# Predication
# -----------------------------------------------------------------------------


def is_opening_component(idf: IDF, component_obj_name: str) -> bool:
    """Return whether a name refers to an Airflow Network opening component."""
    return any(
        aark.ep.obj.has_named(idf, cls_name, component_obj_name)
        for cls_name in OPENING_COMPONENT_CLS_NAMES
    )
