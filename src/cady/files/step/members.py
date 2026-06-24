"""Reconstruct extruded structural members from STEP face lists.

Given the raw face list from :func:`cady.files.step.faces.read_step`, this module
detects end-cap pairs, groups side faces, classifies cross-sections, and
reconstructs extruded members with their centreline axes.

Usage::

    from cady.files.step.faces import read_step
    from cady.files.step.members import extract_members_from_faces

    faces = read_step("frame.stp")
    members = extract_members_from_faces(faces)
    for m in members:
        print(m.name, m.section.section_type)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from cady.domain.vec import Vec3
from cady.files.step.faces import StepFace


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
        na = Vec3.from_xyz(fa.normal)
        for j, fb in enumerate(sorted_faces):
            if j <= i or j in used or fb.normal is None:
                continue
            nb = Vec3.from_xyz(fb.normal)
            if not na.is_parallel(nb):
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

    members: list[ExtrudedMember] = []
    for idx, (cap_a, cap_b) in enumerate(end_cap_pairs):
        axis_start = cap_a.centroid
        axis_end = cap_b.centroid

        extrusion_normal = cap_a.normal
        if extrusion_normal is None:
            continue

        normal_vec = Vec3.from_xyz(extrusion_normal)

        side_faces: list[StepFace] = []
        for f in faces:
            if f is cap_a or f is cap_b:
                continue
            if f.surface_type in ("cylinder", "cone"):
                side_faces.append(f)
            elif f.surface_type == "plane" and f.normal is not None:
                dot = Vec3.from_xyz(f.normal).dot(normal_vec)
                if abs(dot) < 0.01:
                    side_faces.append(f)

        section = classify_section_from_faces(side_faces, cap_a, cap_b)

        members.append(
            ExtrudedMember(
                name=f"M{idx + 1}",
                axis_start=axis_start,
                axis_end=axis_end,
                section=section,
                faces=(cap_a, cap_b, *side_faces),
            )
        )

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
        axis = Vec3.from_xyz(cyl.cylinder_axis)
        radius = cyl.cylinder_radius
        axis_pt = Vec3.from_xyz(cyl.centroid)

        group: list[StepFace] = [cyl]
        assigned.add(i)

        for j in range(len(cylinders)):
            if j in assigned:
                continue
            other = cylinders[j]
            if abs((other.cylinder_radius or 0) - (radius or 0)) > radius_tol:
                continue
            if other.cylinder_axis is None:
                continue
            other_axis = Vec3.from_xyz(other.cylinder_axis)
            if axis.is_parallel(other_axis, tol=axis_tol):
                group.append(other)
                assigned.add(j)

        # Project all cylinder centroids onto the shared axis to find endpoints
        t_values: list[float] = []
        for c in group:
            pt = Vec3.from_xyz(c.centroid)
            t = pt.project_onto_line(axis_pt, axis)
            t_values.append(t)

        if not t_values:
            continue

        t_min = min(t_values)
        t_max = max(t_values)

        if abs(t_max - t_min) < 1e-6:
            # All cylinders share the same reference point — estimate length
            t_min -= 1.0
            t_max += 1.0

        start = (axis_pt + axis * t_min).tuple()
        end = (axis_pt + axis * t_max).tuple()

        members.append(
            ExtrudedMember(
                name=f"M{len(members) + 1}",
                axis_start=start,
                axis_end=end,
                section=ExtrudedSection(
                    section_type="tubular",
                    dimensions={"diameter": radius * 2},
                ),
                faces=tuple(group),
            )
        )

    return members


__all__ = [
    "ExtrudedMember",
    "ExtrudedSection",
    "classify_section_from_faces",
    "extract_members_from_faces",
    "find_end_caps",
    "group_cylinders_into_members",
]
