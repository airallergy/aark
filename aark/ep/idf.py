"""Manipulate EnergyPlus IDFs."""

from typing import TYPE_CHECKING

import aark.ep.field
import aark.ep.geom
import aark.ep.obj

if TYPE_CHECKING:
    from eppy.modeleditor import IDF


_UNNAMED_CLS_NAME2SORT_FIELD_NAMES = {
    "SURFACEPROPERTY:EXPOSEDFOUNDATIONPERIMETER": ["Surface_Name"],
    "AIRFLOWNETWORK:MULTIZONE:ZONE": ["Zone_Name"],
    "AIRFLOWNETWORK:MULTIZONE:SURFACE": ["Surface_Name"],
    "SIZING:ZONE": ["Zone_or_ZoneList_Name"],
    "SIZING:SYSTEM": ["AirLoop_Name"],
    "SIZING:PLANT": ["Plant_or_Condenser_Loop_Name"],
    "ZONEHVAC:EQUIPMENTCONNECTIONS": ["Zone_Name"],
    "OUTDOORAIR:NODELIST": ["Node_or_NodeList_Name_1"],
    "OUTPUT:VARIABLE": ["Variable_Name", "Key_Value"],
    "OUTPUT:METER": ["Key_Name"],
}


def sort(idf: IDF) -> None:
    """Sort objects within each IDF class.

    Notes
    -----
    Sorting may change EnergyPlus behaviour when object order is significant.
    """
    for cls_name, objs in idf.idfobjects.items():
        if len(objs) < 2:
            continue

        if "Name" in objs[0].fieldnames:
            field_names = ["Name"]
        else:
            normalised_cls_name = cls_name.upper()
            if normalised_cls_name not in _UNNAMED_CLS_NAME2SORT_FIELD_NAMES:
                raise NotImplementedError(
                    f"Sorting objects is not implemented for the unnamed class: {cls_name}."
                )

            field_names = _UNNAMED_CLS_NAME2SORT_FIELD_NAMES[normalised_cls_name]

        ordered_objs = sorted(
            objs,
            key=lambda obj: tuple(
                aark.ep.field.normalise(obj[field_name], obj, field_name)
                for field_name in field_names
            ),
        )
        objs.clear()
        objs.extend(ordered_objs)


def format(idf: IDF) -> None:
    """Format an IDF.

    - Remove surrounding whitespace from string field values and trailing empty fields.
    - Set object class names to IDD casing.
    - Round detailed geometry vertices to seven decimal places.
    """
    for objs in idf.idfobjects.values():
        for obj in objs:
            aark.ep.obj.rstrip(obj)
            aark.ep.obj.iddify_cls_name(obj)

            if "Vertex_1_Xcoordinate" in obj.fieldnames:
                aark.ep.geom.round_vertices(obj)
