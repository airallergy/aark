"""Manipulate EnergyPlus geometry objects."""

from collections import Counter
from typing import TYPE_CHECKING

import numpy as np

import aark.ep._pact
import aark.ep.field
import aark.ep.obj

if TYPE_CHECKING:
    from eppy.bunch_subclass import EpBunch
    from eppy.modeleditor import IDF

    from aark.arr import FloatArr2D

# -----------------------------------------------------------------------------
# Affine transformation
# -----------------------------------------------------------------------------


def translator(dx: float, dy: float, dz: float = 0.0) -> FloatArr2D:
    """Create a 4x4 translation matrix."""
    m = np.eye(4, dtype=float)
    m[0, 3] = dx
    m[1, 3] = dy
    m[2, 3] = dz
    return m


def rotator_z(dphi: float) -> FloatArr2D:
    """Create a 4x4 rotation matrix about the Z axis through the origin."""
    c = np.cos(dphi)
    s = np.sin(dphi)

    m = np.eye(4, dtype=float)
    m[0, 0] = c
    m[0, 1] = -s
    m[1, 0] = s
    m[1, 1] = c
    return m


def transform(points: FloatArr2D, transformer: FloatArr2D) -> FloatArr2D:
    """Apply an affine transformation to a set of points with shape (n, 3)."""
    points = np.asarray(points, dtype=float)
    transformer = np.asarray(transformer, dtype=float)

    # sanity check
    _validate_points(points)

    if transformer.shape != (4, 4):
        raise ValueError(f"Expected 4x4 transformation matrix: {transformer}.")

    if not np.allclose(transformer[3, :], [0, 0, 0, 1]):
        raise ValueError(f"Expected affine transformation matrix: {transformer}.")

    # apply the affine transformation
    return points @ transformer[:3, :3].T + transformer[:3, 3]


# -----------------------------------------------------------------------------
# Surface vertices
# -----------------------------------------------------------------------------


def _make_vertex_fields_slicer(obj: EpBunch) -> slice:
    """Make a slicer for the vertex fields of a detailed geometry object."""
    if "Vertex_1_Xcoordinate" not in obj.fieldnames:
        raise ValueError(f"Object has no vertex field: {obj}.")

    start_idx = obj.fieldnames.index("Vertex_1_Xcoordinate")
    return slice(start_idx, None)


def get_vertices(obj: EpBunch) -> FloatArr2D:
    """Get vertices of a detailed geometry object."""
    # read the vertex field values as a 1D list
    slicer = _make_vertex_fields_slicer(obj)
    vertex_field_vals = list(obj.fieldvalues[slicer])

    # sanity check
    if len(vertex_field_vals) % 3 != 0:
        raise ValueError(
            f"Number of vertex field values is not a multiple of 3: {obj}."
        )

    if any(val.strip() == "" for val in vertex_field_vals if isinstance(val, str)):
        raise ValueError(f"Some vertex fields are empty: {obj}.")

    # convert to a 2D array
    vertices = np.array(vertex_field_vals, dtype=float).reshape((-1, 3))
    _validate_vertices(vertices)

    return vertices


def set_vertices(obj: EpBunch, vertices: FloatArr2D) -> None:
    """Set vertices of a detailed geometry object."""
    vertices = np.asarray(vertices, dtype=float)

    # sanity check
    _validate_vertices(vertices)

    # convert to a 1D list
    vertex_field_vals = vertices.reshape(-1).tolist()

    # get the slicer for the vertex fields
    slicer = _make_vertex_fields_slicer(obj)

    # ensure the fieldvalues list is long enough to write the new vertices
    if len(obj.fieldvalues) < slicer.start:
        pad_len = slicer.start - len(obj.fieldvalues)
        obj.fieldvalues.extend([""] * pad_len)

    # write vertices
    obj.fieldvalues[slicer] = vertex_field_vals
    obj.Number_of_Vertices = ""


def set_world_geom_rule(idf: IDF) -> None:
    """Set the coordinate system to `World`."""
    (obj,) = idf.idfobjects["GlobalGeometryRules"]
    obj.Coordinate_System = "World"
    obj.Daylighting_Reference_Point_Coordinate_System = "World"
    obj.Rectangular_Surface_Coordinate_System = "World"


def convert_to_world_coord_sys(idf: IDF) -> None:
    """Convert detailed zone geometry from relative to world coordinates.

    `aark` assumptions
    ------------------
    `Building North Axis` and `Zone Direction of Relative North` are zero or unused.
    """
    # validate aark requirements
    aark.ep._pact.validate_no_building_rel_north(idf)
    aark.ep._pact.validate_no_zone_rel_north(idf)

    # initialise a map of zone names to origins
    zone_name2origin = {}

    # loop through all zone objects
    for obj in idf.idfobjects["Zone"]:
        # get the zone origin
        zone_name2origin[obj.Name] = (
            aark.ep.field.as_float(obj, "X_Origin"),
            aark.ep.field.as_float(obj, "Y_Origin"),
            aark.ep.field.as_float(obj, "Z_Origin"),
        )

        obj.X_Origin = ""
        obj.Y_Origin = ""
        obj.Z_Origin = ""

    # loop through all detailed geometry objects
    for cls_name in ("BuildingSurface:Detailed", "FenestrationSurface:Detailed"):
        for obj in idf.idfobjects[cls_name]:
            # get the origin of the parent zone
            zone_obj = aark.ep.obj.get_zone(obj)
            origin = zone_name2origin[zone_obj.Name]

            # transform the vertices to world coordinates
            vertices = get_vertices(obj)
            transformer = translator(*origin)
            vertices = transform(vertices, transformer)
            set_vertices(obj, vertices)

    # set the world geometry rule
    set_world_geom_rule(idf)


# -----------------------------------------------------------------------------
# Surface generic
# -----------------------------------------------------------------------------


def _make_pair_map(pairs: list[frozenset[str]]) -> dict[str, str]:
    """Make a reciprocal pair map."""
    # sanity check
    for pair in pairs:
        if len(pair) != 2:
            raise ValueError(f"Pair is self-reciprocal: {pair}.")

    for pair, n in Counter(pairs).items():
        if n != 2:
            raise ValueError(f"Pair is not reciprocal: {pair}.")

    # make map
    return dict(sorted(sorted(item) for item in set(pairs)))


def get_pair_maps(idf: IDF) -> tuple[dict[str, str], dict[str, str]]:
    """Get maps of paired surface and subsurface names.

    Each pair is included once, with the key being the lexicographically smaller name.
    """
    # get surface map
    surface_name_pairs = [
        frozenset((obj.Name, obj.Outside_Boundary_Condition_Object))
        for obj in idf.idfobjects["BuildingSurface:Detailed"]
        if aark.ep.field.equal("Surface", obj, "Outside_Boundary_Condition")
    ]
    surface2other_name = _make_pair_map(surface_name_pairs)

    # get subsurface map
    subsurface_name_pairs = [
        frozenset((obj.Name, obj.Outside_Boundary_Condition_Object))
        for obj in idf.idfobjects["FenestrationSurface:Detailed"]
        if not aark.ep.field.equal("", obj, "Outside_Boundary_Condition_Object")
    ]
    subsurface2other_name = _make_pair_map(subsurface_name_pairs)

    # sanity check
    for subsurface_name, other_subsurface_name in subsurface2other_name.items():
        subsurface_obj = aark.ep.obj.get_named(
            idf, "FenestrationSurface:Detailed", subsurface_name
        )
        other_subsurface_obj = aark.ep.obj.get_named(
            idf, "FenestrationSurface:Detailed", other_subsurface_name
        )

        surface_name = subsurface_obj.Building_Surface_Name
        other_surface_name = other_subsurface_obj.Building_Surface_Name

        has_surface = surface_name in surface2other_name
        has_other_surface = other_surface_name in surface2other_name

        assert has_surface != has_other_surface

        if has_surface:
            assert surface2other_name[surface_name] == other_surface_name
        else:
            assert surface2other_name[other_surface_name] == surface_name

    return surface2other_name, subsurface2other_name


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def _validate_points(points: FloatArr2D) -> None:
    """Validate that the point array has shape (n, 3)."""
    # a point array must be 2D
    if points.ndim != 2:
        raise ValueError(f"Expected 2D array: {points}.")

    # a point must have three coordinates
    if points.shape[1] != 3:
        raise ValueError(f"Expected 3 columns: {points}.")


def _validate_vertices(vertices: FloatArr2D) -> None:
    """Validate that the vertex array is compatible with EnergyPlus detailed geometry."""
    # a vertex array must have shape (n, 3)
    _validate_points(vertices)

    # a surface must have at least three vertices
    if vertices.shape[0] < 3:
        raise ValueError(f"Expected at least 3 vertices: {vertices}.")
