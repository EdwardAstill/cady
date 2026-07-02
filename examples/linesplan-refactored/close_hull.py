"""Mirror, cap, weld, and close the lofted linesplan hull.

The lofting process builds the positive-y half of the hull as separate mesh
patches. This process extends selected patch boundaries to the centreline,
mirrors the half hull, caps the keel ends, welds matching vertices, and finally
asks cady to close any remaining mesh boundary loops.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias

from loft_patches import BoundaryNode, LoftedPatch

from cady import Mesh3

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]
Edge: TypeAlias = tuple[int, int]

TOLERANCE = 1e-3
MIRROR_PLANE_ORIGIN: Point3 = (0.0, 0.0, 0.0)
MIRROR_PLANE_NORMAL: Point3 = (0.0, 1.0, 0.0)


@dataclass(frozen=True, slots=True)
class LinesplanHull:
    """All mesh products created while closing the lofted linesplan hull."""

    lofted_patches: tuple[LoftedPatch, ...]
    boundary_extensions: tuple[Mesh3, ...]
    half_meshes: tuple[Mesh3, ...]
    mirrored_meshes: tuple[Mesh3, ...]
    mesh_patches: tuple[Mesh3, ...]
    keel_cap_mesh: Mesh3
    combined_mesh: Mesh3
    closed_mesh: Mesh3


def close_linesplan_hull(lofted_patches: Iterable[LoftedPatch]) -> LinesplanHull:
    """Run the complete hull-closing process for lofted station patches."""
    patches = tuple(lofted_patches)
    boundary_extensions = tuple(
        mesh
        for patch in patches
        for nodes in (patch.yellow_nodes, patch.green_nodes)
        for mesh in boundary_extension_meshes(nodes)
    )
    half_meshes = merge_boundary_extensions(patches, boundary_extensions)
    mirrored_meshes = mirror_meshes(half_meshes)
    mesh_patches = (*half_meshes, *mirrored_meshes)
    keel_cap_mesh = keel_end_cap_mesh(keel_end_rows(keel_boundary_rows(patches)))
    combined_mesh = combine_meshes((*mesh_patches, keel_cap_mesh))
    closed_mesh = combined_mesh.close_mesh(tolerance=TOLERANCE)
    return LinesplanHull(
        lofted_patches=patches,
        boundary_extensions=boundary_extensions,
        half_meshes=half_meshes,
        mirrored_meshes=mirrored_meshes,
        mesh_patches=mesh_patches,
        keel_cap_mesh=keel_cap_mesh,
        combined_mesh=combined_mesh,
        closed_mesh=closed_mesh,
    )


def boundary_extension_meshes(nodes: Iterable[BoundaryNode]) -> tuple[Mesh3, ...]:
    """Build centreline extension strips for contiguous boundary-node chains."""
    meshes: list[Mesh3] = []
    chain: list[BoundaryNode] = []
    for node in sorted(nodes, key=lambda item: item.row_index):
        if chain and node.row_index != chain[-1].row_index + 1:
            meshes.append(boundary_extension_mesh(boundary_node.point for boundary_node in chain))
            chain = []
        chain.append(node)

    if chain:
        meshes.append(boundary_extension_mesh(boundary_node.point for boundary_node in chain))
    return tuple(mesh for mesh in meshes if mesh.vertices)


def boundary_extension_mesh(points: Iterable[Point3]) -> Mesh3:
    """Create a strip from a boundary chain to the y=0 centreline."""
    points = tuple(points)
    if len(points) < 2:
        return Mesh3((), ())

    vertices = list(points)
    projected_indices: list[int] = []
    edges: set[Edge] = set()
    faces: list[Face] = []

    for index, point in enumerate(points):
        if abs(point[1]) <= TOLERANCE:
            projected_indices.append(index)
            continue

        projected_indices.append(len(vertices))
        vertices.append((point[0], 0.0, point[2]))
        edges.add(_edge_key(index, projected_indices[-1]))

    for index in range(len(points) - 1):
        next_index = index + 1
        edges.add(_edge_key(index, next_index))
        edges.add(_edge_key(projected_indices[index], projected_indices[next_index]))
        face = _clean_face(
            (index, next_index, projected_indices[next_index], projected_indices[index])
        )
        if len(face) >= 3:
            faces.append(face)

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def merge_boundary_extensions(
    patches: Iterable[LoftedPatch],
    extensions: Iterable[Mesh3],
) -> tuple[Mesh3, ...]:
    """Attach all centreline extension strips to the first half-hull patch."""
    meshes = [patch.mesh for patch in patches]
    extension_meshes = tuple(mesh for mesh in extensions if mesh.vertices)
    if meshes and extension_meshes:
        meshes[0] = Mesh3.merged((meshes[0], *extension_meshes))
    return tuple(meshes)


def keel_boundary_rows(patches: Iterable[LoftedPatch]) -> tuple[tuple[Point3, ...], ...]:
    """Return the red-top patch rows used for the mirrored keel end caps."""
    rows: list[tuple[Point3, ...]] = []
    for patch in patches:
        if patch.group_index == 1:
            rows.extend(patch.nodes)
    return tuple(sorted(rows, key=lambda row: row[0][0]))


def keel_end_rows(rows: Iterable[tuple[Point3, ...]]) -> tuple[tuple[Point3, ...], ...]:
    """Return only the first and last keel rows that need end caps."""
    rows = tuple(rows)
    if len(rows) <= 2:
        return rows
    return (rows[0], rows[-1])


def keel_end_cap_mesh(rows: Iterable[tuple[Point3, ...]]) -> Mesh3:
    """Build cap faces by joining each keel row to its mirrored row."""
    vertices: list[Point3] = []
    faces: list[Face] = []
    edges: set[Edge] = set()

    for row in rows:
        start = len(vertices)
        vertices.extend((*row, *(_mirror_point(point) for point in reversed(row))))
        face = tuple(range(start, len(vertices)))
        faces.append(face)
        for edge in zip(face, face[1:] + face[:1], strict=True):
            edges.add(_edge_key(*edge))

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def mirror_meshes(meshes: Iterable[Mesh3]) -> tuple[Mesh3, ...]:
    """Mirror the positive-y half hull across the y=0 centreline plane."""
    return tuple(mesh.mirror(MIRROR_PLANE_ORIGIN, MIRROR_PLANE_NORMAL) for mesh in meshes)


def combine_meshes(meshes: Iterable[Mesh3]) -> Mesh3:
    """Merge and weld mesh patches before boundary closure."""
    return weld_mesh(Mesh3.merged(meshes), tolerance=TOLERANCE)


def weld_mesh(mesh: Mesh3, *, tolerance: float) -> Mesh3:
    """Merge vertices whose rounded coordinates match at the given tolerance."""
    index_by_point: dict[tuple[int, int, int], int] = {}
    vertices: list[Point3] = []
    remap: list[int] = []

    for x, y, z in mesh.vertices:
        if abs(y) <= tolerance:
            y = 0.0
        key = (round(x / tolerance), round(y / tolerance), round(z / tolerance))
        if key not in index_by_point:
            index_by_point[key] = len(vertices)
            vertices.append((x, y, z))
        remap.append(index_by_point[key])

    faces: list[Face] = []
    for face in mesh.faces:
        mapped: list[int] = []
        for index in face:
            new_index = remap[index]
            if not mapped or mapped[-1] != new_index:
                mapped.append(new_index)
        if len(mapped) > 1 and mapped[0] == mapped[-1]:
            mapped.pop()

        unique: list[int] = []
        for index in mapped:
            if index not in unique:
                unique.append(index)
        if len(unique) >= 3:
            faces.append(tuple(unique))

    edges: set[Edge] = set()
    for a, b in mesh.edges:
        start, end = remap[a], remap[b]
        if start != end:
            edges.add((min(start, end), max(start, end)))

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def _edge_key(start: int, end: int) -> Edge:
    return (min(start, end), max(start, end))


def _mirror_point(point: Point3) -> Point3:
    return (point[0], -point[1], point[2])


def _clean_face(indices: Iterable[int]) -> Face:
    face: list[int] = []
    for index in indices:
        if not face or face[-1] != index:
            face.append(index)
    if len(face) > 1 and face[0] == face[-1]:
        face.pop()
    return tuple(face)
