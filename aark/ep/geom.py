"""Manipulate geometry of EnergyPlus models."""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF

    type Float64Array2D = np.ndarray[tuple[int, int], np.dtype[np.float64]]


#############################################################################
#######                          EPPY HELPER                          #######
#############################################################################


def _make_vertex_fields_slicer(obj: EpBunch) -> slice:
    """Make a slicer for the vertex fields of a detailed geometry object."""
    if "Vertex_1_Xcoordinate" not in obj.fieldnames:
        raise ValueError(f"Object has no vertex field: {obj}.")

    start = obj.fieldnames.index("Vertex_1_Xcoordinate")
    return slice(start, None)


def _check_vertices(vertices: Float64Array2D) -> None:
    """Check if the vertex array is compatible with EnergyPlus detailed geometry."""
    if vertices.ndim != 2:
        raise ValueError(f"Expected 2D array: {vertices}.")

    if vertices.shape[1] != 3:
        raise ValueError(f"Expected 3 columns: {vertices}.")

    if vertices.shape[0] < 3:
        raise ValueError(f"Expected at least 3 vertices: {vertices}.")


def get_vertices(obj: EpBunch) -> Float64Array2D:
    """Get vertices of a detailed geometry object."""
    # read the vertex field values as a 1D list
    slicer = _make_vertex_fields_slicer(obj)
    vertex_field_values = list(obj.fieldvalues[slicer])

    # sanity check
    if len(vertex_field_values) % 3 != 0:
        raise ValueError(
            f"Number of vertex field values is not a multiple of 3: {obj}."
        )

    if any(v.strip() == "" for v in vertex_field_values if isinstance(v, str)):
        raise ValueError(f"Some vertex fields are empty: {obj}.")

    # convert to a 2D array
    vertices = np.array(vertex_field_values, dtype=float).reshape((-1, 3))
    _check_vertices(vertices)

    return vertices


def set_vertices(obj: EpBunch, vertices: Float64Array2D) -> None:
    """Set vertices of a detailed geometry object."""
    vertices = np.asarray(vertices, dtype=float)

    # sanity check
    _check_vertices(vertices)

    # convert to a 1D list
    vertex_field_values = vertices.reshape(-1).tolist()

    # write vertices
    slicer = _make_vertex_fields_slicer(obj)
    obj.fieldvalues[slicer] = vertex_field_values
    obj.Number_of_Vertices = ""


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


def set_world_geometry_rule(idf: IDF) -> None:
    """Set the coordinate system to World."""
    (obj,) = idf.idfobjects["GLOBALGEOMETRYRULES"]
    obj.Coordinate_System = "World"
    obj.Daylighting_Reference_Point_Coordinate_System = "World"
    obj.Rectangular_Surface_Coordinate_System = "World"


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
