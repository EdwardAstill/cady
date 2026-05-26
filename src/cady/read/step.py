"""Read STEP AP203/AP214 files and extract elementary surface geometry.

Pure Python — no OpenCASCADE, no conda, no compiled dependencies.
Uses ``steputils`` for ISO 10303-21 parsing, then walks the entity
graph to resolve faces, surfaces, and geometry primitives.

Target: Inventor extrusions of structural members.  Complex NURBS
surfaces (B_SPLINE_SURFACE, etc.) are not supported — only elementary
surfaces (PLANE, CYLINDRICAL_SURFACE, CONICAL_SURFACE).

Usage::

    from cady.read.step import read_step

    faces = read_step("part.stp")
    for f in faces:
        print(f.surface_type, f.normal, f.centroid)
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast


@dataclass
class StepFace:
    """A face extracted from a STEP file with resolved geometry."""

    surface_type: str  # "plane", "cylinder", "cone", "unknown"
    centroid: tuple[float, float, float]  # Approximate face centroid
    normal: tuple[float, float, float] | None  # Face normal (planes only)
    area: float  # Approximate area (0 if not computed)
    # Cylinder-specific
    cylinder_axis: tuple[float, float, float] | None
    cylinder_radius: float | None
    # Cone-specific
    cone_apex: tuple[float, float, float] | None
    cone_axis: tuple[float, float, float] | None
    cone_semi_angle: float | None


class _P21Module(Protocol):
    def readfile(self, path: str) -> Any:
        """Read an ISO 10303-21 file."""


def read_step(path: str | Path) -> list[StepFace]:
    """Read a STEP file and return all faces with resolved geometry.

    Args:
        path: Path to a ``.stp`` or ``.step`` file.

    Returns:
        List of StepFace objects, one per ADVANCED_FACE entity found.
    """
    p21 = cast(_P21Module, import_module("steputils.p21"))

    sf = p21.readfile(str(path))
    if not sf.data:
        return []

    ds = sf.data[0]
    resolver = _EntityResolver(ds)
    return list(_extract_faces(ds, resolver))


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------


class _EntityResolver:
    """Resolves STEP references (#123) to their entity objects."""

    def __init__(self, data_section: Any) -> None:
        self._instances = data_section.instances
        self._cache: dict[str, Any] = {}

    def resolve(self, ref: str) -> Any:
        """Resolve a reference string like '#123' to its entity instance."""
        if ref in self._cache:
            return self._cache[ref]
        inst = self._instances.get(ref)
        if inst is None:
            return None
        self._cache[ref] = inst
        return inst

    def resolve_entity(self, ref: str) -> Any | None:
        """Resolve and return the entity object (not the instance wrapper)."""
        inst = self.resolve(ref)
        if inst is None:
            return None
        if hasattr(inst, "entities"):
            # ComplexEntityInstance — return first constituent entity
            return inst.entities[0] if inst.entities else None
        return inst.entity

    def resolve_chain(self, ref: str, *names: str) -> Any | None:
        """Resolve ref, then follow params named *names through references.

        Example: resolve_chain('#4', 'AXIS2_PLACEMENT_3D', 'CARTESIAN_POINT')
        walks #4 → AXIS2_PLACEMENT_3D → param[1] → the CARTESIAN_POINT entity.
        """
        entity = self.resolve_entity(ref)
        if entity is None:
            return None
        for target_name in names:
            found = False
            for param in entity.params:
                if isinstance(param, str) and param.startswith("#"):
                    child = self.resolve_entity(param)
                    if child is not None and child.name == target_name:
                        entity = child
                        found = True
                        break
            if not found:
                return None
        return entity


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _point_from_cartesian(entity: Any) -> tuple[float, float, float]:
    """Extract (x, y, z) from a CARTESIAN_POINT entity."""
    coords = entity.params[1]  # ParameterList
    return (float(coords[0]), float(coords[1]), float(coords[2]))


def _direction(entity: Any) -> tuple[float, float, float]:
    """Extract (dx, dy, dz) from a DIRECTION entity."""
    coords = entity.params[1]  # ParameterList
    return (float(coords[0]), float(coords[1]), float(coords[2]))


def _axis2_placement(entity: Any) -> tuple[
    tuple[float, float, float],  # origin
    tuple[float, float, float],  # axis (Z direction)
    tuple[float, float, float],  # ref_direction (X direction)
]:
    """Extract origin, axis, and ref_direction from AXIS2_PLACEMENT_3D.

    Returns:
        (origin, axis, ref_direction) where all are (x, y, z) tuples.
        If optional ref_direction is missing, returns (1,0,0) as default.
    """
    # params: (name, cartesian_point_ref, axis_ref, [ref_direction_ref])
    origin_entity = _resolve_ref_in_context(entity, entity.params[1])
    axis_entity = _resolve_ref_in_context(entity, entity.params[2])

    origin = _point_from_cartesian(origin_entity) if origin_entity else (0.0, 0.0, 0.0)
    axis = _direction(axis_entity) if axis_entity else (0.0, 0.0, 1.0)

    # ref_direction is optional (param[3] may be None or missing)
    ref_dir = (1.0, 0.0, 0.0)
    if len(entity.params) > 3:
        ref_entity = _resolve_ref_in_context(entity, entity.params[3])
        if ref_entity is not None:
            ref_dir = _direction(ref_entity)

    return origin, axis, ref_dir


def _resolve_ref_in_context(entity: Any, param: Any) -> Any | None:
    """Best-effort reference resolution using the entity's parent data section.

    This is a workaround — the entity objects don't carry a back-reference
    to their DataSection. We use a module-level registry set by _extract_faces.
    """
    if not isinstance(param, str) or not param.startswith("#"):
        return None
    # Try the global registry
    reg = _get_global_resolver()
    if reg is not None:
        return reg.resolve_entity(param)
    return None


_global_resolver: _EntityResolver | None = None


def _get_global_resolver() -> _EntityResolver | None:
    return _global_resolver


def _set_global_resolver(r: _EntityResolver) -> None:
    global _global_resolver
    _global_resolver = r


# ---------------------------------------------------------------------------
# Face extraction
# ---------------------------------------------------------------------------


def _extract_faces(data_section: Any, resolver: _EntityResolver):
    """Yield StepFace objects from all ADVANCED_FACE entities in the data section."""
    _set_global_resolver(resolver)

    # Walk: MANIFOLD_SOLID_BREP → CLOSED_SHELL → ADVANCED_FACE
    for inst in data_section.instances.values():
        entities: list[Any] = []
        if hasattr(inst, "entities"):
            entities.extend(inst.entities)
        elif hasattr(inst, "entity"):
            entities.append(inst.entity)
        for entity in entities:
            if entity.name == "ADVANCED_FACE":
                face = _extract_advanced_face(entity, resolver)
                if face is not None:
                    yield face


def _extract_advanced_face(entity: Any, resolver: _EntityResolver) -> StepFace | None:
    """Extract geometry from an ADVANCED_FACE entity.

    ADVANCED_FACE params:
        [0]: name (str)
        [1]: bounds (ParameterList of FACE_OUTER_BOUND refs)
        [2]: face_geometry (ref to elementary surface)
        [3]: same_sense (bool)
    """
    if len(entity.params) < 3:
        return None

    surface_ref = entity.params[2]
    if not isinstance(surface_ref, str) or not surface_ref.startswith("#"):
        return None

    surface_entity = resolver.resolve_entity(surface_ref)
    if surface_entity is None:
        return None

    return _extract_surface(surface_entity, entity, resolver)


def _extract_surface(
    surface_entity: Any,
    face_entity: Any,
    resolver: _EntityResolver,
) -> StepFace | None:
    """Extract geometry from an elementary surface entity."""
    name = surface_entity.name

    if name == "PLANE":
        return _extract_plane(surface_entity, face_entity, resolver)
    elif name == "CYLINDRICAL_SURFACE":
        return _extract_cylinder(surface_entity, face_entity, resolver)
    elif name == "CONICAL_SURFACE":
        return _extract_cone(surface_entity, face_entity, resolver)

    return StepFace(
        surface_type="unknown",
        centroid=(0.0, 0.0, 0.0),
        normal=None,
        area=0.0,
        cylinder_axis=None,
        cylinder_radius=None,
        cone_apex=None,
        cone_axis=None,
        cone_semi_angle=None,
    )


def _extract_plane(
    surface_entity: Any,
    face_entity: Any,
    resolver: _EntityResolver,
) -> StepFace:
    """PLANE: params[1] is AXIS2_PLACEMENT_3D ref. Normal = axis Z direction."""
    axis_ref = surface_entity.params[1]
    axis_entity = resolver.resolve_entity(str(axis_ref)) if isinstance(axis_ref, str) else None

    origin = (0.0, 0.0, 0.0)
    normal = (0.0, 0.0, 1.0)

    if axis_entity is not None:
        origin, axis_dir, _ = _axis2_placement(axis_entity)
        normal = axis_dir

    centroid = _approximate_centroid(face_entity, resolver, origin)
    area = _approximate_area(face_entity, resolver)

    return StepFace(
        surface_type="plane",
        centroid=centroid,
        normal=normal,
        area=area,
        cylinder_axis=None,
        cylinder_radius=None,
        cone_apex=None,
        cone_axis=None,
        cone_semi_angle=None,
    )


def _extract_cylinder(
    surface_entity: Any,
    face_entity: Any,
    resolver: _EntityResolver,
) -> StepFace:
    """CYLINDRICAL_SURFACE: params[1] is AXIS2_PLACEMENT_3D, params[2] is radius."""
    axis_ref = surface_entity.params[1]
    radius = float(surface_entity.params[2])
    axis_entity = resolver.resolve_entity(str(axis_ref)) if isinstance(axis_ref, str) else None

    origin = (0.0, 0.0, 0.0)
    axis_dir = (0.0, 0.0, 1.0)

    if axis_entity is not None:
        origin, axis_dir, _ = _axis2_placement(axis_entity)

    centroid = _approximate_centroid(face_entity, resolver, origin)

    return StepFace(
        surface_type="cylinder",
        centroid=centroid,
        normal=None,
        area=0.0,
        cylinder_axis=axis_dir,
        cylinder_radius=radius,
        cone_apex=None,
        cone_axis=None,
        cone_semi_angle=None,
    )


def _extract_cone(
    surface_entity: Any,
    face_entity: Any,
    resolver: _EntityResolver,
) -> StepFace:
    """CONICAL_SURFACE: params[1]=AXIS2_PLACEMENT_3D, params[2]=radius, params[3]=semi_angle."""
    axis_ref = surface_entity.params[1]
    semi_angle = float(surface_entity.params[3])
    axis_entity = resolver.resolve_entity(str(axis_ref)) if isinstance(axis_ref, str) else None

    origin = (0.0, 0.0, 0.0)
    axis_dir = (0.0, 0.0, 1.0)

    if axis_entity is not None:
        origin, axis_dir, _ = _axis2_placement(axis_entity)

    centroid = _approximate_centroid(face_entity, resolver, origin)

    return StepFace(
        surface_type="cone",
        centroid=centroid,
        normal=None,
        area=0.0,
        cylinder_axis=None,
        cylinder_radius=None,
        cone_apex=origin,
        cone_axis=axis_dir,
        cone_semi_angle=semi_angle,
    )


# ---------------------------------------------------------------------------
# Face boundary helpers (approximate centroid and area)
# ---------------------------------------------------------------------------


def _approximate_centroid(
    face_entity: Any,
    resolver: _EntityResolver,
    fallback: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Approximate face centroid from boundary vertices.

    Walks ADVANCED_FACE → FACE_OUTER_BOUND → EDGE_LOOP → ORIENTED_EDGE
    → EDGE_CURVE → vertex points. Returns the average of all vertex
    positions as an approximate centroid.
    """
    vertices: list[tuple[float, float, float]] = []
    _collect_face_vertices(face_entity, resolver, vertices)

    if not vertices:
        return fallback

    n = len(vertices)
    return (
        sum(v[0] for v in vertices) / n,
        sum(v[1] for v in vertices) / n,
        sum(v[2] for v in vertices) / n,
    )


def _approximate_area(
    face_entity: Any,
    resolver: _EntityResolver,
) -> float:
    """Approximate face area using the shoelace formula on boundary vertices.

    Only accurate for planar faces. Returns 0.0 if fewer than 3 vertices.
    """
    vertices: list[tuple[float, float, float]] = []
    _collect_face_vertices(face_entity, resolver, vertices)

    if len(vertices) < 3:
        return 0.0

    # Compute face normal from first three vertices
    v0, v1, v2 = vertices[0], vertices[1], vertices[2]
    u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    v = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    nx = u[1] * v[2] - u[2] * v[1]
    ny = u[2] * v[0] - u[0] * v[2]
    nz = u[0] * v[1] - u[1] * v[0]
    n_mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if n_mag < 1e-12:
        return 0.0
    n = (nx / n_mag, ny / n_mag, nz / n_mag)

    # Project vertices onto plane perpendicular to dominant normal axis
    # Find the two axes perpendicular to the normal
    abs_n = (abs(n[0]), abs(n[1]), abs(n[2]))
    if abs_n[0] < abs_n[1] and abs_n[0] < abs_n[2]:
        axis_u = (0.0, -n[2], n[1])
    elif abs_n[1] < abs_n[2]:
        axis_u = (-n[2], 0.0, n[0])
    else:
        axis_u = (-n[1], n[0], 0.0)

    u_mag = math.sqrt(axis_u[0] ** 2 + axis_u[1] ** 2 + axis_u[2] ** 2)
    if u_mag < 1e-12:
        return 0.0
    axis_u = (axis_u[0] / u_mag, axis_u[1] / u_mag, axis_u[2] / u_mag)

    # Second axis = cross(normal, axis_u)
    axis_v = (
        n[1] * axis_u[2] - n[2] * axis_u[1],
        n[2] * axis_u[0] - n[0] * axis_u[2],
        n[0] * axis_u[1] - n[1] * axis_u[0],
    )

    # Project vertices
    origin = vertices[0]
    projected = [
        (
            (p[0] - origin[0]) * axis_u[0]
            + (p[1] - origin[1]) * axis_u[1]
            + (p[2] - origin[2]) * axis_u[2],
            (p[0] - origin[0]) * axis_v[0]
            + (p[1] - origin[1]) * axis_v[1]
            + (p[2] - origin[2]) * axis_v[2],
        )
        for p in vertices
    ]

    # Shoelace formula
    area = 0.0
    for i in range(len(projected)):
        j = (i + 1) % len(projected)
        area += projected[i][0] * projected[j][1]
        area -= projected[j][0] * projected[i][1]

    return abs(area) / 2.0


def _collect_face_vertices(
    face_entity: Any,
    resolver: _EntityResolver,
    vertices: list[tuple[float, float, float]],
) -> None:
    """Walk the ADVANCED_FACE boundary graph and collect all vertex positions.

    ADVANCED_FACE.bounds → FACE_OUTER_BOUND → EDGE_LOOP → ORIENTED_EDGE
    → EDGE_CURVE → edge geometry → vertex points.
    """
    # face_entity.params[1] = bounds (ParameterList of refs)
    if len(face_entity.params) < 2:
        return

    bounds = face_entity.params[1]
    # Could be a single Reference or a ParameterList
    if isinstance(bounds, str) and bounds.startswith("#"):
        bounds = [bounds]
    if not hasattr(bounds, "__iter__"):
        return

    for bound_ref in bounds:
        if not isinstance(bound_ref, str) or not bound_ref.startswith("#"):
            continue
        bound_entity = resolver.resolve_entity(bound_ref)
        if bound_entity is None:
            continue

        # FACE_OUTER_BOUND or FACE_BOUND
        # params[1] = EDGE_LOOP ref
        if len(bound_entity.params) < 2:
            continue
        loop_ref = bound_entity.params[1]
        if not isinstance(loop_ref, str) or not loop_ref.startswith("#"):
            continue

        loop_entity = resolver.resolve_entity(loop_ref)
        if loop_entity is None:
            continue

        # EDGE_LOOP: find the param that contains the oriented edge list.
        # Schema position varies; search for a ParameterList or Reference.
        edge_list: Iterable[object] | None = None
        for param in loop_entity.params:
            if param is not None and param != "" and param != "*":
                if isinstance(param, str) and param.startswith("#"):
                    edge_list = [param]  # Single edge: wrap in list
                    break
                elif hasattr(param, "__iter__") and not isinstance(param, str):
                    edge_list = cast(Iterable[object], param)
                    break

        if edge_list is None:
            continue

        for edge_ref in edge_list:
            if isinstance(edge_ref, tuple):
                edge_ref = cast(tuple[object, ...], edge_ref)[0]
            if not isinstance(edge_ref, str) or not edge_ref.startswith("#"):
                continue

            oriented = resolver.resolve_entity(edge_ref)
            if oriented is None:
                continue

            # ORIENTED_EDGE: params[3] = EDGE_CURVE ref
            if len(oriented.params) < 4:
                continue
            ec_ref = oriented.params[3]
            if not isinstance(ec_ref, str) or not ec_ref.startswith("#"):
                continue

            edge_curve = resolver.resolve_entity(ec_ref)
            if edge_curve is None:
                continue

            # EDGE_CURVE: params[1]=edge_start (VERTEX_POINT or CARTESIAN_POINT),
            #             params[2]=edge_end (VERTEX_POINT or CARTESIAN_POINT),
            #             params[3]=same_sense
            # Or params might have VERTEX_POINT refs that contain CARTESIAN_POINT
            for param_idx in (1, 2):
                if len(edge_curve.params) <= param_idx:
                    continue
                v_ref = edge_curve.params[param_idx]
                if not isinstance(v_ref, str) or not v_ref.startswith("#"):
                    continue

                vertex = resolver.resolve_entity(v_ref)
                if vertex is None:
                    continue

                # Could be VERTEX_POINT (params[1]=CARTESIAN_POINT ref)
                # or directly a CARTESIAN_POINT
                if vertex.name == "VERTEX_POINT":
                    if len(vertex.params) > 1:
                        cp_ref = vertex.params[1]
                        if isinstance(cp_ref, str) and cp_ref.startswith("#"):
                            cp = resolver.resolve_entity(cp_ref)
                            if cp is not None and cp.name == "CARTESIAN_POINT":
                                vertices.append(_point_from_cartesian(cp))
                elif vertex.name == "CARTESIAN_POINT":
                    vertices.append(_point_from_cartesian(vertex))
