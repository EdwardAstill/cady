"""Greedy advancing-front surface reconstruction from an unnormalised 3D point cloud.

This is a small, dependency-light prototype intended for CAD/library adaptation.
It does NOT try to be CGAL.  It is useful for clean-ish, moderately uniform
point clouds where you want an open surface and you do not have supplied normals.

Core idea:
    1. Pick a seed triangle from nearby points.
    2. Its boundary edges form the active front.
    3. For each front edge, choose a nearby point on the opposite side of the
       edge from the existing triangle, forming a new triangle.
    4. Add the triangle, update the front, and continue until no candidate works.

The algorithm leaves unmatched front edges as open boundaries.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from math import inf
from typing import Literal, TypeAlias, overload

import numpy as np
from numpy.typing import NDArray

Point3: TypeAlias = tuple[float, float, float]
FaceIndex: TypeAlias = tuple[int, int, int]
EdgeIndex: TypeAlias = tuple[int, int]


@dataclass(frozen=True, slots=True)
class AdvancingFrontStats:
    """Simple reconstruction diagnostics."""

    vertices: int
    faces: int
    boundary_edges: int
    max_edge_length: float


@dataclass(frozen=True, slots=True)
class AdvancingFrontMeshData:
    """Primitive mesh data reconstructed by the advancing-front operation."""

    vertices: tuple[Point3, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...]


@dataclass(frozen=True, slots=True)
class AdvancingFrontResult:
    """Primitive mesh data plus useful reconstruction diagnostics."""

    mesh: AdvancingFrontMeshData
    stats: AdvancingFrontStats


@overload
def advancing_front_surface(
    points: object,
    *,
    tolerance: float = 1e-6,
    max_edge_length: float | None = None,
    neighbour_count: int = 40,
    search_radius_factor: float = 1.75,
    max_faces: int | None = None,
    return_stats: Literal[False] = False,
) -> AdvancingFrontMeshData: ...


@overload
def advancing_front_surface(
    points: object,
    *,
    tolerance: float = 1e-6,
    max_edge_length: float | None = None,
    neighbour_count: int = 40,
    search_radius_factor: float = 1.75,
    max_faces: int | None = None,
    return_stats: Literal[True],
) -> AdvancingFrontResult: ...


def advancing_front_surface(
    points: object,
    *,
    tolerance: float = 1e-6,
    max_edge_length: float | None = None,
    neighbour_count: int = 40,
    search_radius_factor: float = 1.75,
    max_faces: int | None = None,
    return_stats: bool = False,
) -> AdvancingFrontMeshData | AdvancingFrontResult:
    """Reconstruct an open triangle mesh from points using a greedy front.

    Parameters
    ----------
    points:
        Iterable or array of ``(x, y, z)`` points.

    tolerance:
        Geometric epsilon for duplicate points, degenerate triangles, and side
        tests.

    max_edge_length:
        Maximum accepted triangle edge length.  If None, it is estimated from
        the median nearest-neighbour spacing.

    neighbour_count:
        Number of nearest candidate points considered around each front edge.
        Higher is more robust but slower.

    search_radius_factor:
        Candidate radius multiplier relative to ``max_edge_length``.

    max_faces:
        Optional hard stop for debugging.

    return_stats:
        If True, return ``AdvancingFrontResult`` instead of just mesh data.

    Returns
    -------
    AdvancingFrontMeshData or AdvancingFrontResult
        Open surface mesh data.  Boundary edges are expected; this method does
        not force watertight closure.
    """
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if neighbour_count < 6:
        raise ValueError("neighbour_count should be at least 6")
    if search_radius_factor <= 1.0:
        raise ValueError("search_radius_factor must be greater than 1")

    pts = _coerce_points(points, tolerance=tolerance)
    if len(pts) < 3:
        raise ValueError("at least three points are required")

    pts = _dedupe_points(pts, tolerance=tolerance)
    if len(pts) < 3:
        raise ValueError("point cloud collapsed to fewer than three unique points")

    if max_edge_length is None:
        max_edge_length = _estimate_max_edge_length(pts, tolerance=tolerance)
    max_edge_length = float(max_edge_length)
    if max_edge_length <= tolerance:
        raise ValueError("max_edge_length is too small")

    min_area = tolerance * tolerance
    seed = _find_seed_triangle(
        pts,
        max_edge_length=max_edge_length,
        neighbour_count=neighbour_count,
        min_area=min_area,
    )
    if seed is None:
        raise ValueError("could not find a valid seed triangle; increase max_edge_length")

    faces: list[FaceIndex] = []
    face_keys: set[tuple[int, int, int]] = set()
    edge_faces: dict[EdgeIndex, list[int]] = defaultdict(list)
    front: deque[EdgeIndex] = deque()
    queued: set[EdgeIndex] = set()

    _add_face(
        faces,
        face_keys,
        edge_faces,
        front,
        queued,
        seed,
    )

    while front:
        if max_faces is not None and len(faces) >= max_faces:
            break

        edge = front.popleft()
        queued.discard(edge)

        # The edge may have been closed by a different front expansion.
        if len(edge_faces[edge]) != 1:
            continue

        a, b = edge
        if _distance(pts[a], pts[b]) > max_edge_length + tolerance:
            continue

        candidate = _best_candidate_for_edge(
            pts,
            edge,
            faces,
            face_keys,
            edge_faces,
            max_edge_length=max_edge_length,
            search_radius=max_edge_length * search_radius_factor,
            neighbour_count=neighbour_count,
            min_area=min_area,
            tolerance=tolerance,
        )
        if candidate is None:
            continue

        face = _oriented_adjacent_face(edge, candidate, faces[edge_faces[edge][0]])
        _add_face(faces, face_keys, edge_faces, front, queued, face)

    used_vertices = sorted({index for face in faces for index in face})
    if not used_vertices:
        raise ValueError("reconstruction produced no faces")

    mesh = _compact_mesh(pts, tuple(faces), used_vertices)
    boundary_count = len(_boundary_edges(mesh.faces))
    stats = AdvancingFrontStats(
        vertices=len(mesh.vertices),
        faces=len(mesh.faces),
        boundary_edges=boundary_count,
        max_edge_length=max_edge_length,
    )

    if return_stats:
        return AdvancingFrontResult(mesh=mesh, stats=stats)
    return mesh


# ── Candidate selection ─────────────────────────────────────────────


def _best_candidate_for_edge(
    pts: NDArray[np.float64],
    edge: EdgeIndex,
    faces: Sequence[FaceIndex],
    face_keys: set[tuple[int, int, int]],
    edge_faces: dict[EdgeIndex, list[int]],
    *,
    max_edge_length: float,
    search_radius: float,
    neighbour_count: int,
    min_area: float,
    tolerance: float,
) -> int | None:
    a, b = edge
    pa = pts[a]
    pb = pts[b]
    midpoint = 0.5 * (pa + pb)

    existing_face = faces[edge_faces[edge][0]]
    existing_third = _third_vertex(existing_face, edge)
    if existing_third is None:
        return None

    neighbour_ids = _nearest_indices(pts, midpoint, count=neighbour_count + 3)
    local_ids = [idx for idx in neighbour_ids if _distance(pts[idx], midpoint) <= search_radius]
    if len(local_ids) < 4:
        local_ids = list(neighbour_ids)

    normal = _local_plane_normal(pts, local_ids)
    edge_vector = pb - pa
    existing_side = float(np.dot(np.cross(edge_vector, pts[existing_third] - pa), normal))

    best_index: int | None = None
    best_score = inf

    for c in local_ids:
        if c in (a, b, existing_third):
            continue

        key = _face_key((a, b, c))
        if key in face_keys:
            continue

        ac = _edge_key(a, c)
        bc = _edge_key(b, c)

        # The front edge already has one incident face and would become closed.
        # The two new edges must not already be saturated.
        if len(edge_faces.get(ac, ())) >= 2 or len(edge_faces.get(bc, ())) >= 2:
            continue

        la = _distance(pts[a], pts[c])
        lb = _distance(pts[b], pts[c])
        lab = _distance(pts[a], pts[b])
        if la > max_edge_length + tolerance or lb > max_edge_length + tolerance:
            continue

        area = _triangle_area(pts[a], pts[b], pts[c])
        if area <= min_area:
            continue

        candidate_side = float(np.dot(np.cross(edge_vector, pts[c] - pa), normal))
        # Candidate must be on the opposite side of the active edge from the
        # triangle already attached to that edge.
        if (
            abs(existing_side) > tolerance
            and abs(candidate_side) > tolerance
            and existing_side * candidate_side >= 0.0
        ):
            continue

        # Shape score: prefer compact, non-skinny triangles that are not much
        # larger than the current front edge.
        lengths = np.array([lab, la, lb], dtype=np.float64)
        shortest = float(np.min(lengths))
        longest = float(np.max(lengths))
        if shortest <= tolerance:
            continue

        aspect = longest / shortest
        perimeter = float(np.sum(lengths))
        score = aspect * 3.0 + perimeter / max_edge_length

        if score < best_score:
            best_score = score
            best_index = c

    return best_index


def _find_seed_triangle(
    pts: NDArray[np.float64],
    *,
    max_edge_length: float,
    neighbour_count: int,
    min_area: float,
) -> FaceIndex | None:
    best: FaceIndex | None = None
    best_score = inf

    for a in range(len(pts)):
        neighbours = _nearest_indices(pts, pts[a], count=min(neighbour_count + 1, len(pts)))
        neighbours = [idx for idx in neighbours if idx != a]

        for i, b in enumerate(neighbours):
            ab = _distance(pts[a], pts[b])
            if ab > max_edge_length:
                continue
            for c in neighbours[i + 1 :]:
                ac = _distance(pts[a], pts[c])
                bc = _distance(pts[b], pts[c])
                if ac > max_edge_length or bc > max_edge_length:
                    continue
                area = _triangle_area(pts[a], pts[b], pts[c])
                if area <= min_area:
                    continue
                lengths = np.array([ab, ac, bc], dtype=np.float64)
                score = (
                    float(np.max(lengths) / np.min(lengths))
                    + float(np.sum(lengths)) / max_edge_length
                )
                if score < best_score:
                    best_score = score
                    best = (a, b, c)

    return best


# ── Front bookkeeping ───────────────────────────────────────────────


def _add_face(
    faces: list[FaceIndex],
    face_keys: set[tuple[int, int, int]],
    edge_faces: dict[EdgeIndex, list[int]],
    front: deque[EdgeIndex],
    queued: set[EdgeIndex],
    face: FaceIndex,
) -> None:
    key = _face_key(face)
    if key in face_keys:
        return

    face_index = len(faces)
    faces.append(face)
    face_keys.add(key)

    for edge in _face_edges(face):
        edge_faces[edge].append(face_index)
        count = len(edge_faces[edge])
        if count == 1 and edge not in queued:
            front.append(edge)
            queued.add(edge)
        elif count >= 2 and edge in queued:
            queued.remove(edge)
            # Removing from deque in-place is O(n), but this is a prototype.
            with suppress(ValueError):
                front.remove(edge)


def _oriented_adjacent_face(
    edge: EdgeIndex,
    candidate: int,
    existing_face: FaceIndex,
) -> FaceIndex:
    """Orient a new face so the shared edge is traversed opposite to existing."""
    a, b = edge
    if _face_contains_directed_edge(existing_face, a, b):
        return (b, a, candidate)
    return (a, b, candidate)


def _face_contains_directed_edge(face: FaceIndex, a: int, b: int) -> bool:
    x, y, z = face
    return (x == a and y == b) or (y == a and z == b) or (z == a and x == b)


def _third_vertex(face: FaceIndex, edge: EdgeIndex) -> int | None:
    a, b = edge
    for index in face:
        if index != a and index != b:
            return index
    return None


# ── Point and mesh helpers ──────────────────────────────────────────


def _coerce_points(points: object, *, tolerance: float) -> NDArray[np.float64]:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must have shape (n, 3)")
    finite = np.all(np.isfinite(array), axis=1)
    array = array[finite]
    return np.asarray(array, dtype=np.float64)


def _dedupe_points(points: NDArray[np.float64], *, tolerance: float) -> NDArray[np.float64]:
    # Grid-hash duplicate removal.  Keeps the first point in each tolerance cell.
    inv = 1.0 / tolerance
    seen: set[tuple[int, int, int]] = set()
    kept: list[NDArray[np.float64]] = []
    for point in points:
        key = (
            int(round(float(point[0]) * inv)),
            int(round(float(point[1]) * inv)),
            int(round(float(point[2]) * inv)),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(point)
    return np.asarray(kept, dtype=np.float64)


def _estimate_max_edge_length(points: NDArray[np.float64], *, tolerance: float) -> float:
    if len(points) < 2:
        return tolerance
    nn: list[float] = []
    for i, point in enumerate(points):
        diff = points - point
        d2 = np.einsum("ij,ij->i", diff, diff)
        d2[i] = inf
        value = float(np.sqrt(np.min(d2)))
        if np.isfinite(value) and value > tolerance:
            nn.append(value)
    if not nn:
        return tolerance * 10.0
    # 2.75 is deliberately generous: fronts need to bridge more than one exact
    # nearest-neighbour spacing when samples are not perfectly regular.
    return float(np.median(np.asarray(nn, dtype=np.float64)) * 2.75)


def _nearest_indices(
    points: NDArray[np.float64],
    centre: NDArray[np.float64],
    *,
    count: int,
) -> list[int]:
    diff = points - centre
    d2 = np.einsum("ij,ij->i", diff, diff)
    count = max(1, min(int(count), len(points)))
    indices = np.argpartition(d2, count - 1)[:count]
    return [int(i) for i in indices[np.argsort(d2[indices])]]


def _local_plane_normal(points: NDArray[np.float64], indices: Sequence[int]) -> NDArray[np.float64]:
    local = points[list(indices)]
    if len(local) < 3:
        return np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
    centred = local - np.mean(local, axis=0)
    try:
        _, _, vt = np.linalg.svd(centred, full_matrices=False)
    except np.linalg.LinAlgError:
        return np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
    normal = vt[-1]
    norm = float(np.linalg.norm(normal))
    if norm == 0.0:
        return np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
    return normal / norm


def _compact_mesh(
    points: NDArray[np.float64],
    faces: tuple[FaceIndex, ...],
    used_vertices: Sequence[int],
) -> AdvancingFrontMeshData:
    remap = {old: new for new, old in enumerate(used_vertices)}
    vertices: tuple[Point3, ...] = tuple(
        (float(points[index, 0]), float(points[index, 1]), float(points[index, 2]))
        for index in used_vertices
    )
    remapped_faces: tuple[FaceIndex, ...] = tuple(
        (remap[a], remap[b], remap[c])
        for a, b, c in faces
        if a in remap and b in remap and c in remap
    )
    edges = _edges_from_faces(remapped_faces)
    return AdvancingFrontMeshData(vertices, remapped_faces, edges)


def _face_edges(face: FaceIndex) -> tuple[EdgeIndex, EdgeIndex, EdgeIndex]:
    a, b, c = face
    return (_edge_key(a, b), _edge_key(b, c), _edge_key(c, a))


def _edge_key(a: int, b: int) -> EdgeIndex:
    return (a, b) if a < b else (b, a)


def _face_key(face: FaceIndex) -> tuple[int, int, int]:
    a, b, c = sorted(face)
    return (a, b, c)


def _edges_from_faces(faces: Sequence[FaceIndex]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        edges.update(_face_edges(face))
    return tuple(sorted(edges))


def _boundary_edges(faces: Sequence[FaceIndex]) -> tuple[EdgeIndex, ...]:
    counts: dict[EdgeIndex, int] = defaultdict(int)
    for face in faces:
        for edge in _face_edges(face):
            counts[edge] += 1
    return tuple(edge for edge, count in counts.items() if count == 1)


def _distance(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    return float(np.linalg.norm(a - b))


def _triangle_area(a: NDArray[np.float64], b: NDArray[np.float64], c: NDArray[np.float64]) -> float:
    return 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))


__all__ = [
    "AdvancingFrontMeshData",
    "AdvancingFrontResult",
    "AdvancingFrontStats",
    "advancing_front_surface",
]
