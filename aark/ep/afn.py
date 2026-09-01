"""Manipulate EnergyPlus AirflowNetwork objects."""

from typing import TYPE_CHECKING

from CoolProp.CoolProp import PropsSI

import aark.ep.field

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF


REF_TEMPERATURE = 20  # °C
REF_PRESSURE = 101325  # Pa
REF_HUMIDITY_RATIO = 0  # kg water kg-1 dry air
REF_AIR_DENSITY = float(  # float is not needed in coolprop 8 with typing
    PropsSI("Dmass", "T", REF_TEMPERATURE + 273.15, "P", REF_PRESSURE, "Air")
)  # kg m-3  # assumes REF_HUMIDITY_RATIO == 0


def get_surface_obj(idf: IDF, surface_name: str) -> EpBunch:
    """Get a unique AirflowNetwork surface object linked to a surface."""
    objs = [
        obj
        for obj in idf.idfobjects["AirflowNetwork:MultiZone:Surface"]
        if aark.ep.field.equal(surface_name, obj, "Surface_Name")
    ]

    if not objs:
        raise ValueError(f"Missing AirflowNetwork surface object: {surface_name}.")

    if len(objs) > 1:
        raise ValueError(f"Duplicate AirflowNetwork surface objects: {surface_name}.")

    return objs[0]
