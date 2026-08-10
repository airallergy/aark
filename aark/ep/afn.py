"""Manipulate EnergyPlus AirflowNetwork objects."""

from typing import TYPE_CHECKING

import aark.ep.field

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF


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
