"""Manipulate EnergyPlus geometry."""

from typing import TYPE_CHECKING

import numpy as np

import aark.ep.generic

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF

    type Float64Array2D = np.ndarray[tuple[int, int], np.dtype[np.float64]]

#############################################################################
#######                     AFFINE TRANSFORMATION                     #######
#############################################################################


def _check_points(points: Float64Array2D) -> None:
    """Check if the point array has shape (n, 3)."""
    if points.ndim != 2:
        raise ValueError(f"Expected 2D array: {points}.")

    if points.shape[1] != 3:
        raise ValueError(f"Expected 3 columns: {points}.")


def translator(dx: float, dy: float, dz: float = 0.0) -> Float64Array2D:
    """Create a 4x4 translation matrix."""
    m = np.eye(4, dtype=float)
    m[0, 3] = dx
    m[1, 3] = dy
    m[2, 3] = dz
    return m


def rotator_z(dphi_rad: float) -> Float64Array2D:
    """Create a 4x4 rotation matrix about the Z axis through the origin."""
    c = np.cos(dphi_rad)
    s = np.sin(dphi_rad)

    m = np.eye(4, dtype=float)
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m


def transform(points: Float64Array2D, transformer: Float64Array2D) -> Float64Array2D:
    """Apply an affine transformation to a set of points with shape (n, 3)."""
    points = np.asarray(points, dtype=float)
    transformer = np.asarray(transformer, dtype=float)

    # sanity check
    _check_points(points)

    if transformer.shape != (4, 4):
        raise ValueError(f"Expected 4x4 transformation matrix: {transformer}.")

    if not np.allclose(transformer[3, :], [0, 0, 0, 1]):
        raise ValueError(f"Expected affine transformation matrix: {transformer}.")

    # apply the affine transformation
    return points @ transformer[:3, :3].T + transformer[:3, 3]


#############################################################################
#######                       SURFACE VERTICES                        #######
#############################################################################


def _make_vertex_fields_slicer(obj: EpBunch) -> slice:
    """Make a slicer for the vertex fields of a detailed geometry object."""
    if "Vertex_1_Xcoordinate" not in obj.fieldnames:
        raise ValueError(f"Object has no vertex field: {obj}.")

    start = obj.fieldnames.index("Vertex_1_Xcoordinate")
    return slice(start, None)


def _check_vertices(vertices: Float64Array2D) -> None:
    """Check if the vertex array is compatible with EnergyPlus detailed geometry."""
    _check_points(vertices)

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


def set_world_geometry_rule(idf: IDF) -> None:
    """Set the coordinate system to World."""
    (obj,) = idf.idfobjects["GLOBALGEOMETRYRULES"]
    obj.Coordinate_System = "World"
    obj.Daylighting_Reference_Point_Coordinate_System = "World"
    obj.Rectangular_Surface_Coordinate_System = "World"


def convert_to_world_coordinate_system(idf: IDF) -> None:
    """Convert detailed zone geometry from relative to world coordinates.

    Assumes Building North Axis and Zone Direction of Relative North are zero or unused.
    """
    # check the building relative north
    (building_obj,) = idf.idfobjects["BUILDING"]

    if not np.isclose(
        aark.ep.generic.get_field_value_as_float(building_obj, "North_Axis"), 0
    ):
        raise ValueError(f"Building.North_Axis is not zero: {building_obj}.")

    building_obj.North_Axis = ""

    # initialise a map of zone names to origins
    zone_name2origin = {}

    # loop through all zone objects
    for obj in idf.idfobjects["ZONE"]:
        # check the zone relative north
        if not np.isclose(
            aark.ep.generic.get_field_value_as_float(
                obj, "Direction_of_Relative_North"
            ),
            0,
        ):
            raise ValueError(f"Zone.Direction_of_Relative_North is not zero: {obj}.")

        obj.Direction_of_Relative_North = ""

        # get the zone origin
        zone_name2origin[obj.Name] = (
            aark.ep.generic.get_field_value_as_float(obj, "X_Origin"),
            aark.ep.generic.get_field_value_as_float(obj, "Y_Origin"),
            aark.ep.generic.get_field_value_as_float(obj, "Z_Origin"),
        )

        obj.X_Origin = ""
        obj.Y_Origin = ""
        obj.Z_Origin = ""

    # loop through all detailed geometry objects
    for class_name in ("BUILDINGSURFACE:DETAILED", "FENESTRATIONSURFACE:DETAILED"):
        for obj in idf.idfobjects[class_name]:
            # get the origin of the parent zone
            zone_name = aark.ep.generic.get_zone_name(obj)
            origin = zone_name2origin[zone_name]

            # transform the vertices to world coordinates
            vertices = get_vertices(obj)
            transformer = translator(*origin)
            vertices = transform(vertices, transformer)
            set_vertices(obj, vertices)

    # set the world geometry rule
    set_world_geometry_rule(idf)
