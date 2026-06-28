"""Read STEP AP203/AP214 files and extract elementary surface geometry.

Pure Python; no OpenCASCADE, no conda, no compiled dependencies.
Uses ``steputils`` for ISO 10303-21 parsing, then walks the entity
graph to resolve faces, surfaces, and geometry primitives.

Target: Inventor extrusions of structural members.  Complex NURBS
surfaces (B_SPLINE_SURFACE, etc.) are not supported; only elementary
surfaces (PLANE, CYLINDRICAL_SURFACE, CONICAL_SURFACE).

Usage::


    faces = read_step("part.stp")
    for f in faces:
        print(f.surface_type, f.normal, f.centroid)
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol, cast

from cady.errors import WriteError
from cady.files.utils import mesh_from_target
from cady.geometry import Mesh3
from cady.operations.coordinates import (
    add3,
    dot3,
    is_parallel3,
    project_onto_line3,
    scale3,
)


@dataclass(frozen=True, slots=True)
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


def _as_step_ref(value: object) -> str | None:
    """Return a STEP entity reference like ``#123`` if present."""
    if isinstance(value, str) and value.startswith("#"):
        return value
    return None


def _iter_step_refs(value: object) -> Iterable[str]:
    """Yield STEP references from a scalar ref, tuple wrapper, or iterable."""
    ref = _as_step_ref(value)
    if ref is not None:
        yield ref
        return
    if isinstance(value, tuple) and value:
        ref = _as_step_ref(cast(tuple[object, ...], value)[0])
        if ref is not None:
            yield ref
        return
    if isinstance(value, str) or not isinstance(value, Iterable):
        return
    for item in cast(Iterable[object], value):
        yield from _iter_step_refs(item)


def _resolve_ref_entity(resolver: _EntityResolver, value: object) -> Any | None:
    """Resolve a STEP reference value to its entity, returning ``None`` if absent."""
    ref = _as_step_ref(value)
    if ref is None:
        return None
    return resolver.resolve_entity(ref)


def _iter_resolved_entities(resolver: _EntityResolver, value: object) -> Iterable[Any]:
    """Yield resolved entities for all STEP references contained in ``value``."""
    for ref in _iter_step_refs(value):
        entity = resolver.resolve_entity(ref)
        if entity is not None:
            yield entity


def _axis2_placement(
    entity: Any,
    resolver: _EntityResolver,
) -> tuple[
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
    origin_entity = _resolve_ref_entity(resolver, entity.params[1])
    axis_entity = _resolve_ref_entity(resolver, entity.params[2])

    origin = _point_from_cartesian(origin_entity) if origin_entity else (0.0, 0.0, 0.0)
    axis = _direction(axis_entity) if axis_entity else (0.0, 0.0, 1.0)

    # ref_direction is optional (param[3] may be None or missing)
    ref_dir = (1.0, 0.0, 0.0)
    if len(entity.params) > 3:
        ref_entity = _resolve_ref_entity(resolver, entity.params[3])
        if ref_entity is not None:
            ref_dir = _direction(ref_entity)

    return origin, axis, ref_dir


# ---------------------------------------------------------------------------
# Face extraction
# ---------------------------------------------------------------------------


def _extract_faces(data_section: Any, resolver: _EntityResolver):
    """Yield StepFace objects from all ADVANCED_FACE entities in the data section."""
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
        origin, axis_dir, _ = _axis2_placement(axis_entity, resolver)
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
        origin, axis_dir, _ = _axis2_placement(axis_entity, resolver)

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
        origin, axis_dir, _ = _axis2_placement(axis_entity, resolver)

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


def _normal_from_points(
    points: list[tuple[float, float, float]],
) -> tuple[float, float, float] | None:
    """Return a unit normal from the first three points, if they are not colinear."""
    if len(points) < 3:
        return None
    v0, v1, v2 = points[0], points[1], points[2]
    u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    v = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    nx = u[1] * v[2] - u[2] * v[1]
    ny = u[2] * v[0] - u[0] * v[2]
    nz = u[0] * v[1] - u[1] * v[0]
    magnitude = math.sqrt(nx * nx + ny * ny + nz * nz)
    if magnitude < 1e-12:
        return None
    return (nx / magnitude, ny / magnitude, nz / magnitude)


def _plane_projection_axes(
    normal: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """Build orthonormal in-plane axes for a face normal."""
    abs_n = (abs(normal[0]), abs(normal[1]), abs(normal[2]))
    if abs_n[0] < abs_n[1] and abs_n[0] < abs_n[2]:
        axis_u = (0.0, -normal[2], normal[1])
    elif abs_n[1] < abs_n[2]:
        axis_u = (-normal[2], 0.0, normal[0])
    else:
        axis_u = (-normal[1], normal[0], 0.0)

    magnitude = math.sqrt(axis_u[0] ** 2 + axis_u[1] ** 2 + axis_u[2] ** 2)
    if magnitude < 1e-12:
        return None
    axis_u = (axis_u[0] / magnitude, axis_u[1] / magnitude, axis_u[2] / magnitude)
    axis_v = (
        normal[1] * axis_u[2] - normal[2] * axis_u[1],
        normal[2] * axis_u[0] - normal[0] * axis_u[2],
        normal[0] * axis_u[1] - normal[1] * axis_u[0],
    )
    return axis_u, axis_v


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

    normal = _normal_from_points(vertices)
    if normal is None:
        return 0.0
    axes = _plane_projection_axes(normal)
    if axes is None:
        return 0.0
    axis_u, axis_v = axes

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
    for edge_curve in _iter_face_edge_curves(face_entity, resolver):
        for point in _iter_edge_curve_vertices(edge_curve, resolver):
            vertices.append(point)


def _iter_face_bounds(face_entity: Any, resolver: _EntityResolver) -> Iterable[Any]:
    """Yield resolved FACE_BOUND/FACE_OUTER_BOUND entities for a face."""
    if len(face_entity.params) < 2:
        return
    yield from _iter_resolved_entities(resolver, face_entity.params[1])


def _loop_edge_list(loop_entity: Any) -> Iterable[object]:
    """Return the oriented-edge list parameter from an EDGE_LOOP entity."""
    for param in loop_entity.params:
        if param in (None, "", "*"):
            continue
        if _as_step_ref(param) is not None:
            return [param]
        if not isinstance(param, str) and isinstance(param, Iterable):
            return cast(Iterable[object], param)
    return ()


def _iter_bound_oriented_edges(bound_entity: Any, resolver: _EntityResolver) -> Iterable[Any]:
    """Yield ORIENTED_EDGE entities referenced by a face bound."""
    if len(bound_entity.params) < 2:
        return
    loop_entity = _resolve_ref_entity(resolver, bound_entity.params[1])
    if loop_entity is None:
        return
    yield from _iter_resolved_entities(resolver, _loop_edge_list(loop_entity))


def _iter_face_edge_curves(face_entity: Any, resolver: _EntityResolver) -> Iterable[Any]:
    """Yield EDGE_CURVE entities referenced by all bounds of a face."""
    for bound_entity in _iter_face_bounds(face_entity, resolver):
        for oriented in _iter_bound_oriented_edges(bound_entity, resolver):
            if len(oriented.params) < 4:
                continue
            edge_curve = _resolve_ref_entity(resolver, oriented.params[3])
            if edge_curve is not None:
                yield edge_curve


def _iter_edge_curve_vertices(
    edge_curve: Any,
    resolver: _EntityResolver,
) -> Iterable[tuple[float, float, float]]:
    """Yield start/end vertex positions for an EDGE_CURVE."""
    for param_idx in (1, 2):
        if len(edge_curve.params) <= param_idx:
            continue
        vertex = _resolve_ref_entity(resolver, edge_curve.params[param_idx])
        if vertex is None:
            continue
        point = _vertex_point(vertex, resolver)
        if point is not None:
            yield point


def _vertex_point(
    vertex_entity: Any,
    resolver: _EntityResolver,
) -> tuple[float, float, float] | None:
    """Resolve a VERTEX_POINT or CARTESIAN_POINT entity to coordinates."""
    if vertex_entity.name == "CARTESIAN_POINT":
        return _point_from_cartesian(vertex_entity)
    if vertex_entity.name != "VERTEX_POINT" or len(vertex_entity.params) <= 1:
        return None
    cartesian = _resolve_ref_entity(resolver, vertex_entity.params[1])
    if cartesian is None or cartesian.name != "CARTESIAN_POINT":
        return None
    return _point_from_cartesian(cartesian)

# src/cady/write/step/ids.py


class IdAllocator:
    """Sequential entity ID counter and registry for a STEP DATA section."""

    def __init__(self) -> None:
        self._n = 0
        self._lines: list[str] = []

    def add(self, definition: str) -> int:
        self._n += 1
        self._lines.append(f"#{self._n}={definition};")
        return self._n

    def render_data(self) -> str:
        return "\n".join(self._lines)

"""Reconstruct extruded structural members from STEP face lists.

Given the raw face list from :func:`cady.files.step.read_step`, this module
detects end-cap pairs, groups side faces, classifies cross-sections, and
reconstructs extruded members with their centreline axes.

Usage::


    faces = read_step("frame.stp")
    members = extract_members_from_faces(faces)
    for m in members:
        print(m.name, m.section.section_type)
"""





def _empty_dimensions() -> Mapping[str, float]:
    return MappingProxyType({})


def _empty_faces() -> tuple[StepFace, ...]:
    return ()


# ── Data types ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExtrudedSection:
    """Cross-section of an extruded structural member.

    Attributes:
        section_type: One of ``"tubular"``, ``"i_beam"``, ``"box"``,
            ``"channel"``, ``"angle"``, ``"tee"``, or ``"unknown"``.
        dimensions: Named dimensions in metres (e.g. ``{"diameter": 0.3}``).
    """

    section_type: str
    dimensions: Mapping[str, float] = field(default_factory=_empty_dimensions)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))


@dataclass(frozen=True, slots=True)
class ExtrudedMember:
    """A structural member reconstructed from a STEP solid extrusion.

    Attributes:
        name: Human-readable identifier (e.g. ``"M1"``).
        axis_start: Centroid of the first end cap.
        axis_end: Centroid of the second end cap.
        section: Cross-section classification.
        faces: The StepFace objects belonging to this member (end caps + side faces).
    """

    name: str
    axis_start: tuple[float, float, float]
    axis_end: tuple[float, float, float]
    section: ExtrudedSection
    faces: tuple[StepFace, ...] = field(default_factory=_empty_faces)

    def __post_init__(self) -> None:
        object.__setattr__(self, "faces", tuple(self.faces))


# ── End-cap detection ───────────────────────────────────────────────────────


def find_end_caps(
    planar_faces: list[StepFace],
    *,
    area_min_ratio: float = 0.1,
) -> list[tuple[StepFace, StepFace]]:
    """Find parallel planar face pairs that are likely end caps of extrusions.

    Matches pairs of planes with opposite-facing normals, similar area, and
    among the largest planar faces in the set.

    Args:
        planar_faces: Pre-filtered list of faces with ``surface_type == "plane"``.
        area_min_ratio: Minimum area ratio between paired faces (default 0.1).

    Returns:
        List of ``(face_a, face_b)`` pairs.
    """
    if not planar_faces:
        return []

    pairs: list[tuple[StepFace, StepFace]] = []
    used: set[int] = set()

    sorted_faces = sorted(planar_faces, key=lambda f: f.area, reverse=True)

    for i, fa in enumerate(sorted_faces):
        if i in used or fa.normal is None:
            continue
        na = fa.normal
        for j, fb in enumerate(sorted_faces):
            if j <= i or j in used or fb.normal is None:
                continue
            nb = fb.normal
            if not is_parallel3(na, nb):
                continue
            if fa.area < fb.area * area_min_ratio or fb.area < fa.area * area_min_ratio:
                continue
            pairs.append((fa, fb))
            used.add(i)
            used.add(j)
            break

    if not pairs:
        return []

    max_area = max(max(a.area, b.area) for a, b in pairs)
    return [
        (a, b)
        for a, b in pairs
        if a.area >= max_area * 0.5 and b.area >= max_area * 0.5
    ]


# ── Section classification ──────────────────────────────────────────────────


def classify_section_from_faces(
    side_faces: list[StepFace],
    end_cap_a: StepFace,
    end_cap_b: StepFace,
) -> ExtrudedSection:
    """Infer cross-section type from the side faces of an extrusion.

    Args:
        side_faces: Faces between the two end caps.
        end_cap_a: First end-cap face.
        end_cap_b: Second end-cap face.

    Returns:
        An ``ExtrudedSection`` with the best-guess type and dimensions.
    """
    cylinder_count = sum(1 for f in side_faces if f.surface_type == "cylinder")
    plane_count = sum(1 for f in side_faces if f.surface_type == "plane")

    if cylinder_count >= 1 and plane_count == 0:
        for f in side_faces:
            if f.surface_type == "cylinder" and f.cylinder_radius is not None:
                return ExtrudedSection(
                    section_type="tubular",
                    dimensions={"diameter": f.cylinder_radius * 2},
                )

    if plane_count == 4:
        return ExtrudedSection(section_type="box")

    if 7 <= plane_count <= 12:
        return ExtrudedSection(section_type="i_beam")

    if 5 <= plane_count <= 6:
        return ExtrudedSection(section_type="channel")

    if 3 <= plane_count <= 4:
        return ExtrudedSection(section_type="angle")

    return ExtrudedSection(section_type="unknown")


# ── Member extraction ───────────────────────────────────────────────────────


def extract_members_from_faces(faces: list[StepFace]) -> list[ExtrudedMember]:
    """Extract structural members from a face list using end-cap detection.

    Works for prismatic extrusions: tubes, I-beams, boxes, channels, angles.
    Does not require pythonocc-core — operates on pre-extracted StepFace objects.

    Algorithm:
        1. Separate planar faces from curved faces.
        2. Find parallel planar face pairs (end caps).
        3. For each pair, the centroid line is the member centreline.
        4. All remaining faces between the end caps are side faces.
        5. Classify section type from side faces.

    Returns:
        List of ``ExtrudedMember`` objects.
    """
    planar = [f for f in faces if f.surface_type == "plane"]
    end_cap_pairs = find_end_caps(planar)
    members = [
        member
        for idx, pair in enumerate(end_cap_pairs, start=1)
        if (member := _member_from_end_caps(faces, pair, idx)) is not None
    ]

    # Fallback: tube fast-path via cylinder grouping (no end caps found)
    if not members:
        tubular = group_cylinders_into_members(faces)
        members.extend(tubular)

    return members


# ── Tube fast-path ──────────────────────────────────────────────────────────


def group_cylinders_into_members(
    faces: list[StepFace],
    *,
    axis_tol: float = 1e-6,
    radius_tol: float = 0.001,
) -> list[ExtrudedMember]:
    """Group cylindrical faces into tubular structural members.

    Cylinders are grouped if they share a colinear axis and the same radius.
    Each group becomes an ``ExtrudedMember`` with endpoints computed from
    face centroid projections onto the shared axis.

    This is the fast path for tubular frames where end-cap planes are not
    explicitly modelled.
    """
    cylinders = [
        f
        for f in faces
        if f.surface_type == "cylinder"
        and f.cylinder_axis is not None
        and f.cylinder_radius is not None
    ]
    if not cylinders:
        return []

    members: list[ExtrudedMember] = []
    assigned: set[int] = set()

    for i in range(len(cylinders)):
        if i in assigned:
            continue

        cyl = cylinders[i]
        if cyl.cylinder_axis is None or cyl.cylinder_radius is None:
            continue
        group = _collect_colinear_cylinder_group(
            cylinders,
            seed_index=i,
            assigned=assigned,
            axis_tol=axis_tol,
            radius_tol=radius_tol,
        )
        endpoints = _cylinder_group_endpoints(group)
        if endpoints is None:
            continue
        start, end = endpoints

        members.append(
            ExtrudedMember(
                name=f"M{len(members) + 1}",
                axis_start=start,
                axis_end=end,
                section=ExtrudedSection(
                    section_type="tubular",
                    dimensions={"diameter": cyl.cylinder_radius * 2},
                ),
                faces=tuple(group),
            )
        )

    return members


def _member_from_end_caps(
    faces: list[StepFace],
    pair: tuple[StepFace, StepFace],
    index: int,
) -> ExtrudedMember | None:
    """Build one member candidate from a matched end-cap pair."""
    cap_a, cap_b = pair
    if cap_a.normal is None:
        return None
    side_faces = _side_faces_for_end_caps(faces, cap_a, cap_b)
    section = classify_section_from_faces(side_faces, cap_a, cap_b)
    return ExtrudedMember(
        name=f"M{index}",
        axis_start=cap_a.centroid,
        axis_end=cap_b.centroid,
        section=section,
        faces=(cap_a, cap_b, *side_faces),
    )


def _side_faces_for_end_caps(
    faces: list[StepFace],
    cap_a: StepFace,
    cap_b: StepFace,
) -> list[StepFace]:
    """Collect non-cap faces that plausibly lie on the extrusion sides."""
    if cap_a.normal is None:
        return []
    normal_vec = cap_a.normal
    side_faces: list[StepFace] = []
    for face in faces:
        if face is cap_a or face is cap_b:
            continue
        if face.surface_type in ("cylinder", "cone"):
            side_faces.append(face)
            continue
        if face.surface_type == "plane" and face.normal is not None:
            dot = dot3(face.normal, normal_vec)
            if abs(dot) < 0.01:
                side_faces.append(face)
    return side_faces


def _collect_colinear_cylinder_group(
    cylinders: list[StepFace],
    *,
    seed_index: int,
    assigned: set[int],
    axis_tol: float,
    radius_tol: float,
) -> list[StepFace]:
    """Group cylinders that share the same radius and axis direction."""
    seed = cylinders[seed_index]
    if seed.cylinder_axis is None or seed.cylinder_radius is None:
        return []
    axis = seed.cylinder_axis
    radius = float(seed.cylinder_radius)

    group: list[StepFace] = [seed]
    assigned.add(seed_index)

    for index, other in enumerate(cylinders):
        if index in assigned or other.cylinder_axis is None or other.cylinder_radius is None:
            continue
        if abs(other.cylinder_radius - radius) > radius_tol:
            continue
        if is_parallel3(axis, other.cylinder_axis, tolerance=axis_tol):
            group.append(other)
            assigned.add(index)

    return group


def _cylinder_group_endpoints(
    group: list[StepFace],
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    """Estimate tubular member endpoints from grouped cylinder centroids."""
    if not group or group[0].cylinder_axis is None:
        return None
    axis = group[0].cylinder_axis
    axis_point = group[0].centroid
    projections = [
        project_onto_line3(face.centroid, axis_point, axis)
        for face in group
    ]
    if not projections:
        return None

    t_min = min(projections)
    t_max = max(projections)
    if abs(t_max - t_min) < 1e-6:
        t_min -= 1.0
        t_max += 1.0

    return (
        add3(axis_point, scale3(axis, t_min)),
        add3(axis_point, scale3(axis, t_max)),
    )


__all__ = [
    "ExtrudedMember",
    "ExtrudedSection",
    "classify_section_from_faces",
    "extract_members_from_faces",
    "find_end_caps",
    "group_cylinders_into_members",
]

read_step_faces = read_step


def render(target: object, *, tolerance: float = 1e-3) -> str:
    """Render a mesh-coercible target as a minimal STEP AP214-style document."""
    mesh = _mesh_from_target(target, tolerance=tolerance)
    if not mesh.faces:
        raise WriteError("cannot write empty STEP mesh")
    lines = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION(('cady mesh export'),'2;1');",
        "FILE_NAME('cady.step','',('cady'),('cady'),'cady','cady','');",
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN_CC2'));",
        "ENDSEC;",
        "DATA;",
    ]
    next_id = 1
    vertex_ids: list[int] = []
    for vertex in mesh.vertices:
        # Vertices are emitted once, then referenced from each face loop.
        vertex_id = next_id
        next_id += 1
        vertex_ids.append(vertex_id)
        lines.append(
            f"#{vertex_id}=CARTESIAN_POINT('',({vertex[0]:.12g},{vertex[1]:.12g},{vertex[2]:.12g}));"
        )
    for a, b, c in mesh.faces:
        face_id = next_id
        next_id += 1
        lines.append(f"#{face_id}=POLY_LOOP('',(#{vertex_ids[a]},#{vertex_ids[b]},#{vertex_ids[c]}));")
    lines.extend(["ENDSEC;", "END-ISO-10303-21;"])
    return "\n".join(lines) + "\n"


def write(target: object, path: str | Path, *, tolerance: float = 1e-3) -> object:
    """Write a mesh-coercible target to ``path`` as STEP text."""
    Path(path).write_text(render(target, tolerance=tolerance), encoding="ascii")
    return target


def read_faces(path: str | Path) -> list[StepFace]:
    """Read STEP faces with resolved elementary-surface metadata."""
    return read_step(path)


def read_members(path: str | Path) -> list[ExtrudedMember]:
    """Read a STEP file and reconstruct extruded members from its faces."""
    return extract_members_from_faces(read_faces(path))


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3:
    return mesh_from_target(target, tolerance=tolerance)


__all__ = [
    "ExtrudedMember",
    "ExtrudedSection",
    "IdAllocator",
    "StepFace",
    "classify_section_from_faces",
    "extract_members_from_faces",
    "find_end_caps",
    "group_cylinders_into_members",
    "read_faces",
    "read_members",
    "read_step",
    "read_step_faces",
    "render",
    "write",
]
