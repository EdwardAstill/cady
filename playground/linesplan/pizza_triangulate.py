"""Pizza triangulation: convert non-triangular mesh faces to triangles.

Quad faces (4 vertices) are split diagonally into 2 triangles.
N-gon faces (5+ vertices) try a pizza/pie centre fill first. If that misses
the minimum angle target, they use up to three reduced inner polygon rings.
If the ring strategy still misses the target, the polygon is split across the
best internal chord and each child polygon is triangulated the same way.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from math import acos, degrees, pi
from typing import TypeAlias

import numpy as np

from cady import Camera, DisplayStyle, Mesh3, Scene

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]
Triangle: TypeAlias = list[int]

PIZZA_MIN_ANGLE_DEGREES = 15.0
PIZZA_MAX_INNER_RINGS = 3
PIZZA_MAX_SPLIT_DEPTH = 8
INNER_RING_START_SCALE = 0.12
INNER_RING_SCALE_STEP = 0.04
INNER_RING_MAX_SCALE = 0.58
MIN_SPLIT_AREA_RATIO = 0.08


def pizza_triangulate_mesh(mesh: Mesh3) -> Mesh3:
    """Return a new Mesh3 with all faces triangulated using the pizza strategy.

    Quad faces are split along their shorter diagonal.
    N-gon faces get up to three reduced inner polygon rings and a centre fill.
    If that still misses the angle target, the face is split recursively.
    Existing triangle faces pass through unchanged.
    Display edges are recomputed from the triangulated faces so every
    triangle edge is visible.
    """
    new_vertices, new_faces = pizza_triangulate(mesh.vertices, mesh.faces)
    new_edges = _face_edges(new_faces)
    return Mesh3(
        tuple(tuple(v) for v in new_vertices),  # type: ignore[arg-type]
        tuple(tuple(f) for f in new_faces),  # type: ignore[arg-type]
        tuple(sorted(new_edges)),
    )


def pizza_triangulate(
    vertices: Sequence[Point3] | np.ndarray,
    faces: Sequence[Sequence[int]] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert faces to all-triangle faces.

    Parameters
    ----------
    vertices : (n, 3) array or sequence of points
        Vertex positions.
    faces : (m, k) array or sequence of index sequences
        Face vertex indices. Each face may have any number of vertices >= 3.

    Returns
    -------
    new_vertices : np.ndarray of shape (n + added, 3)
        Original vertices plus inserted ring and centroid vertices.
    new_faces : np.ndarray of shape (t, 3)
        All-triangle face index array.
    """
    V = np.asarray(vertices, dtype=np.float64)

    if isinstance(faces, np.ndarray) and faces.ndim == 2:
        iterable = [list(row) for row in faces]
    else:
        iterable = list(faces)

    new_vertices: list[list[float]] = list(V.tolist())
    new_face_list: list[list[int]] = []

    for face in iterable:
        ids = _clean_face(face)
        n = len(ids)

        if n < 3:
            continue

        if n == 3:
            new_face_list.append(ids)

        elif n == 4:
            new_face_list.extend(_split_quad(V, ids))

        else:
            new_face_list.extend(_triangulate_ngon(V, ids, new_vertices))

    if not new_face_list:
        return (
            np.array(new_vertices, dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
        )

    return (
        np.array(new_vertices, dtype=np.float64),
        np.array(new_face_list, dtype=np.int64),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_face(face: Iterable[int]) -> list[int]:
    """Remove consecutive duplicates and trailing wrap-around duplicate."""
    ids: list[int] = []
    for x in face:
        ix = int(x)
        if ix < 0:
            continue
        if not ids or ids[-1] != ix:
            ids.append(ix)
    if len(ids) > 1 and ids[0] == ids[-1]:
        ids.pop()
    return ids


def _split_quad(V: np.ndarray, ids: list[int]) -> list[list[int]]:
    """Split a quad into two triangles along the shorter diagonal."""
    a, b, c, d = ids
    diag_ac = float(np.linalg.norm(V[c] - V[a]))
    diag_bd = float(np.linalg.norm(V[d] - V[b]))

    if diag_ac <= diag_bd:
        return [[a, b, c], [a, c, d]]
    else:
        return [[a, b, d], [b, c, d]]


def _face_edges(faces: np.ndarray) -> set[tuple[int, int]]:
    """Extract all unique edges from an (n, 3) triangle face array."""
    edges: set[tuple[int, int]] = set()
    for tri in faces:
        a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        edges.add((a, b) if a < b else (b, a))
        edges.add((b, c) if b < c else (c, b))
        edges.add((c, a) if c < a else (a, c))
    return edges


def _triangulate_ngon(
    _V: np.ndarray,
    ids: list[int],
    new_vertices: list[list[float]],
    split_depth: int = 0,
) -> list[Triangle]:
    """Use centre fill, then rings, then split if the angle target still fails."""
    trial_vertices = [list(vertex) for vertex in new_vertices]
    final_faces = _fan_ids_to_centroid(ids, trial_vertices)
    final_angle = _min_triangle_angle(
        np.asarray(trial_vertices, dtype=np.float64),
        final_faces,
    )
    if final_angle + 1e-9 >= PIZZA_MIN_ANGLE_DEGREES:
        new_vertices[:] = trial_vertices
        return final_faces

    if len(ids) <= 4:
        return _fan_ids_to_centroid(ids, new_vertices)

    ring_vertices = [list(vertex) for vertex in new_vertices]
    ring_faces = _try_inner_rings(ids, ring_vertices)
    ring_angle = _min_triangle_angle(np.asarray(ring_vertices, dtype=np.float64), ring_faces)
    if ring_angle + 1e-9 >= PIZZA_MIN_ANGLE_DEGREES:
        new_vertices[:] = ring_vertices
        return ring_faces

    if split_depth < PIZZA_MAX_SPLIT_DEPTH:
        split = _best_chord_split(np.asarray(new_vertices, dtype=np.float64), ids)
        if split is not None:
            first, second = _split_polygon_with_midpoint(ids, *split, new_vertices)
            return [
                *(_triangulate_child_polygon(first, new_vertices, split_depth + 1)),
                *(_triangulate_child_polygon(second, new_vertices, split_depth + 1)),
            ]

    new_vertices[:] = ring_vertices
    return ring_faces


def _triangulate_child_polygon(
    ids: list[int],
    new_vertices: list[list[float]],
    split_depth: int,
) -> list[Triangle]:
    if len(ids) < 3:
        return []
    if len(ids) == 3:
        return [ids]
    if len(ids) == 4:
        return _split_quad(np.asarray(new_vertices, dtype=np.float64), ids)
    return _triangulate_ngon(
        np.asarray(new_vertices, dtype=np.float64),
        ids,
        new_vertices,
        split_depth,
    )


def _try_inner_rings(
    ids: list[int],
    new_vertices: list[list[float]],
) -> list[Triangle]:
    """Add up to three rings and return the best full triangulation found."""
    best_vertices = [list(vertex) for vertex in new_vertices]
    best_faces = _fan_ids_to_centroid(ids, best_vertices)
    best_angle = _min_triangle_angle(np.asarray(best_vertices, dtype=np.float64), best_faces)

    trial_vertices = [list(vertex) for vertex in new_vertices]
    current_ids = list(ids)
    ring_faces: list[Triangle] = []

    for _ in range(PIZZA_MAX_INNER_RINGS):
        candidate = _next_inner_ring(np.asarray(trial_vertices, dtype=np.float64), current_ids)
        if candidate is None:
            break

        inner_points, faces = candidate
        inner_start = len(trial_vertices)
        for point in inner_points:
            trial_vertices.append(point.tolist())
        current_ids = list(range(inner_start, inner_start + len(inner_points)))
        ring_faces.extend(faces)

        final_vertices = [list(vertex) for vertex in trial_vertices]
        final_faces = [list(face) for face in ring_faces]
        final_faces.extend(_fan_ids_to_centroid(current_ids, final_vertices))
        final_angle = _min_triangle_angle(
            np.asarray(final_vertices, dtype=np.float64),
            final_faces,
        )

        if final_angle > best_angle:
            best_angle = final_angle
            best_vertices = final_vertices
            best_faces = final_faces
        if final_angle + 1e-9 >= PIZZA_MIN_ANGLE_DEGREES:
            new_vertices[:] = final_vertices
            return final_faces

    new_vertices[:] = best_vertices
    return best_faces


def _next_inner_ring(
    V: np.ndarray,
    ids: list[int],
) -> tuple[tuple[np.ndarray, ...], list[Triangle]] | None:
    inner_count = _inner_polygon_vertex_count(len(ids))
    if inner_count >= len(ids):
        return None

    best_points: tuple[np.ndarray, ...] | None = None
    best_faces: list[Triangle] = []
    best_angle = -1.0

    for inner_points in _scaled_inner_rings(V, ids, inner_count):
        trial_vertices = [list(vertex) for vertex in V.tolist()]
        faces = _band_faces_to_inner_polygon(ids, inner_points, trial_vertices)
        angle = _min_triangle_angle(np.asarray(trial_vertices, dtype=np.float64), faces)
        if angle > best_angle:
            best_angle = angle
            best_points = inner_points
            best_faces = faces
        if angle + 1e-9 >= PIZZA_MIN_ANGLE_DEGREES:
            return inner_points, faces

    if best_points is None:
        return None
    return best_points, best_faces


def _scaled_inner_rings(
    V: np.ndarray,
    ids: list[int],
    inner_count: int,
) -> tuple[tuple[np.ndarray, ...], ...]:
    centre = np.mean(V[np.asarray(ids, dtype=np.int64)], axis=0)
    groups = _outer_index_groups(len(ids), inner_count)
    directions = tuple(_group_direction(V, ids, group, centre) for group in groups)
    boundary_distances = tuple(
        _ray_boundary_distance(V, ids, centre, direction) for direction in directions
    )

    rings: list[tuple[np.ndarray, ...]] = []
    scale = INNER_RING_START_SCALE
    while scale <= INNER_RING_MAX_SCALE + 1e-12:
        rings.append(
            tuple(
                centre + direction * boundary_distance * scale
                for direction, boundary_distance in zip(
                    directions,
                    boundary_distances,
                    strict=True,
                )
            )
        )
        scale += INNER_RING_SCALE_STEP
    return tuple(rings)


def _inner_polygon_vertex_count(outer_count: int) -> int:
    if outer_count <= 5:
        return 3
    target = int(round(outer_count * 0.45))
    return max(3, min(outer_count - 1, target))


def _outer_index_groups(outer_count: int, inner_count: int) -> tuple[tuple[int, ...], ...]:
    groups: list[tuple[int, ...]] = []
    for index in range(inner_count):
        start = round(index * outer_count / inner_count)
        end = round((index + 1) * outer_count / inner_count)
        groups.append(tuple(range(start, max(start + 1, end))))
    groups[-1] = tuple(range(groups[-1][0], outer_count))
    return tuple(groups)


def _group_direction(
    V: np.ndarray,
    ids: list[int],
    group: tuple[int, ...],
    centre: np.ndarray,
) -> np.ndarray:
    group_points = V[np.asarray([ids[index % len(ids)] for index in group], dtype=np.int64)]
    direction = np.mean(group_points, axis=0) - centre
    length = float(np.linalg.norm(direction))
    if length <= 0.0:
        angle = 2.0 * pi * group[0] / len(ids)
        return np.asarray((float(np.cos(angle)), float(np.sin(angle)), 0.0), dtype=np.float64)
    return direction / length


def _ray_boundary_distance(
    V: np.ndarray,
    ids: list[int],
    centre: np.ndarray,
    direction: np.ndarray,
) -> float:
    distances = [
        _ray_segment_distance(centre, direction, V[ids[index]], V[ids[(index + 1) % len(ids)]])
        for index in range(len(ids))
    ]
    positive = [distance for distance in distances if distance is not None and distance > 0.0]
    if positive:
        return min(positive)
    fallback = max(float(np.linalg.norm(V[index] - centre)) for index in ids)
    return fallback if fallback > 0.0 else 1.0


def _ray_segment_distance(
    origin: np.ndarray,
    direction: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
) -> float | None:
    segment = end - start
    normal = np.cross(direction, segment)
    normal_norm_sq = float(np.dot(normal, normal))
    if normal_norm_sq <= 1e-18:
        return None
    diff = start - origin
    distance = float(np.dot(np.cross(diff, segment), normal) / normal_norm_sq)
    ratio = float(np.dot(np.cross(diff, direction), normal) / normal_norm_sq)
    if distance <= 0.0 or ratio < -1e-9 or ratio > 1.0 + 1e-9:
        return None
    return distance


def _band_faces_to_inner_polygon(
    ids: list[int],
    inner_points: tuple[np.ndarray, ...],
    new_vertices: list[list[float]],
) -> list[Triangle]:
    inner_start = len(new_vertices)
    for point in inner_points:
        new_vertices.append(point.tolist())

    outer_count = len(ids)
    inner_count = len(inner_points)
    sector_by_outer_index = tuple(
        min(inner_count - 1, int(index * inner_count / outer_count))
        for index in range(outer_count)
    )

    faces: list[Triangle] = []
    for index in range(outer_count):
        next_index = (index + 1) % outer_count
        sector = sector_by_outer_index[index]
        next_sector = sector_by_outer_index[next_index]
        a = ids[index]
        b = ids[next_index]
        c = inner_start + next_sector
        d = inner_start + sector
        if sector == next_sector:
            faces.append([a, b, d])
        else:
            faces.extend(_split_quad(np.asarray(new_vertices, dtype=np.float64), [a, b, c, d]))

    return faces


def _best_chord_split(V: np.ndarray, ids: list[int]) -> tuple[int, int] | None:
    if len(ids) < 6:
        return None

    points = _project_polygon_points(V, ids)
    best_split: tuple[int, int] | None = None
    best_score = -1.0

    for start in range(len(ids)):
        for end in range(start + 2, len(ids)):
            if start == 0 and end == len(ids) - 1:
                continue

            if not _is_valid_chord(points, start, end):
                continue

            first = ids[start : end + 1]
            second = [*ids[end:], *ids[: start + 1]]
            score = _split_compactness_score(V, first, second)
            if score is None:
                continue
            if score > best_score:
                best_score = score
                best_split = (start, end)

    return best_split


def _split_polygon_with_midpoint(
    ids: list[int],
    start: int,
    end: int,
    new_vertices: list[list[float]],
) -> tuple[list[int], list[int]]:
    first_id = ids[start]
    second_id = ids[end]
    midpoint = [
        (new_vertices[first_id][axis] + new_vertices[second_id][axis]) * 0.5
        for axis in range(3)
    ]
    midpoint_id = len(new_vertices)
    new_vertices.append(midpoint)

    return (
        [*ids[start : end + 1], midpoint_id],
        [*ids[end:], *ids[: start + 1], midpoint_id],
    )


def _project_polygon_points(V: np.ndarray, ids: list[int]) -> tuple[tuple[float, float], ...]:
    pts = V[np.asarray(ids, dtype=np.int64)]
    normal = np.zeros(3, dtype=np.float64)
    for index, point in enumerate(pts):
        next_point = pts[(index + 1) % len(pts)]
        normal[0] += (point[1] - next_point[1]) * (point[2] + next_point[2])
        normal[1] += (point[2] - next_point[2]) * (point[0] + next_point[0])
        normal[2] += (point[0] - next_point[0]) * (point[1] + next_point[1])

    drop_axis = int(np.argmax(np.abs(normal)))
    axes = tuple(axis for axis in range(3) if axis != drop_axis)
    return tuple((float(point[axes[0]]), float(point[axes[1]])) for point in pts)


def _is_valid_chord(
    points: tuple[tuple[float, float], ...],
    start: int,
    end: int,
) -> bool:
    a = points[start]
    b = points[end]
    for index in range(len(points)):
        next_index = (index + 1) % len(points)
        if index in (start, end) or next_index in (start, end):
            continue
        if _segments_intersect(a, b, points[index], points[next_index]):
            return False

    midpoint = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
    return _point_in_polygon(midpoint, points)


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)

    if o1 * o2 < 0.0 and o3 * o4 < 0.0:
        return True
    if abs(o1) <= 1e-9 and _point_on_segment(c, a, b):
        return True
    if abs(o2) <= 1e-9 and _point_on_segment(d, a, b):
        return True
    if abs(o3) <= 1e-9 and _point_on_segment(a, c, d):
        return True
    return abs(o4) <= 1e-9 and _point_on_segment(b, c, d)


def _orientation(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    return (
        min(start[0], end[0]) - 1e-9 <= point[0] <= max(start[0], end[0]) + 1e-9
        and min(start[1], end[1]) - 1e-9 <= point[1] <= max(start[1], end[1]) + 1e-9
    )


def _point_in_polygon(
    point: tuple[float, float],
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        if _point_on_segment(point, previous, current):
            return True
        crosses = (current[1] > y) != (previous[1] > y)
        if crosses:
            x_at_y = (previous[0] - current[0]) * (y - current[1]) / (
                previous[1] - current[1]
            ) + current[0]
            if x < x_at_y:
                inside = not inside
        previous = current
    return inside


def _split_compactness_score(
    V: np.ndarray,
    first: list[int],
    second: list[int],
) -> float | None:
    first_area = _polygon_area(V, first)
    second_area = _polygon_area(V, second)
    larger_area = max(first_area, second_area)
    if larger_area <= 1e-12:
        return None
    if min(first_area, second_area) / larger_area < MIN_SPLIT_AREA_RATIO:
        return None

    first_quality = _polygon_compactness(V, first)
    second_quality = _polygon_compactness(V, second)
    worst_quality = min(first_quality, second_quality)
    average_quality = (first_quality + second_quality) * 0.5
    return 0.8 * worst_quality + 0.2 * average_quality


def _polygon_compactness(V: np.ndarray, ids: list[int]) -> float:
    area = _polygon_area(V, ids)
    perimeter = _polygon_perimeter(V, ids)
    if perimeter <= 1e-12:
        return 0.0
    return 4.0 * pi * area / (perimeter * perimeter)


def _polygon_area(V: np.ndarray, ids: list[int]) -> float:
    pts = V[np.asarray(ids, dtype=np.int64)]
    area_vector = np.zeros(3, dtype=np.float64)
    for index, point in enumerate(pts):
        area_vector += np.cross(point, pts[(index + 1) % len(pts)])
    return 0.5 * float(np.linalg.norm(area_vector))


def _polygon_perimeter(V: np.ndarray, ids: list[int]) -> float:
    return sum(
        float(np.linalg.norm(V[ids[index]] - V[ids[(index + 1) % len(ids)]]))
        for index in range(len(ids))
    )


def _fan_ids_to_centroid(
    ids: list[int],
    new_vertices: list[list[float]],
) -> list[Triangle]:
    if len(ids) < 3:
        return []
    if len(ids) == 3:
        return [list(ids)]
    return _fan_from_centroid(np.asarray(new_vertices, dtype=np.float64), ids, new_vertices)


def _fan_from_centroid(
    V: np.ndarray,
    ids: list[int],
    new_vertices: list[list[float]],
) -> list[Triangle]:
    """Fallback: add a centroid vertex and fan triangles to each polygon edge."""
    centroid_idx = len(new_vertices)
    pts = V[np.asarray(ids, dtype=np.int64)]
    centroid: list[float] = np.mean(pts, axis=0).tolist()
    new_vertices.append(centroid)

    n = len(ids)
    tris: list[Triangle] = []
    for i in range(n):
        tris.append([ids[i], ids[(i + 1) % n], centroid_idx])

    return tris


def _min_triangle_angle(V: np.ndarray, faces: Sequence[Sequence[int]]) -> float:
    if not faces:
        return 0.0
    return min(_triangle_min_angle(V, face) for face in faces)


def _triangle_min_angle(V: np.ndarray, face: Sequence[int]) -> float:
    a, b, c = (int(index) for index in face)
    ab = float(np.linalg.norm(V[a] - V[b]))
    bc = float(np.linalg.norm(V[b] - V[c]))
    ca = float(np.linalg.norm(V[c] - V[a]))
    return min(
        _angle_degrees(ab, ca, bc),
        _angle_degrees(ab, bc, ca),
        _angle_degrees(bc, ca, ab),
    )


def _angle_degrees(first: float, second: float, opposite: float) -> float:
    denominator = 2.0 * first * second
    if denominator <= 0.0:
        return 0.0
    cosine = (first * first + second * second - opposite * opposite) / denominator
    return degrees(acos(max(-1.0, min(1.0, cosine))))


def example_meshes() -> tuple[tuple[str, Mesh3, Mesh3], ...]:
    """Return example polygon meshes and their reduced-inner triangulations."""
    examples = (
        (
            "arched twelve edge polygon",
            (
                (0.0, 0.0, 0.0),
                (1.0, 1.9, 0.0),
                (2.4, 3.5, 0.0),
                (4.1, 4.4, 0.0),
                (6.0, 4.45, 0.0),
                (7.8, 4.0, 0.0),
                (9.2, 2.9, 0.0),
                (10.0, 1.35, 0.0),
                (10.1, 0.0, 0.0),
                (7.0, 0.0, 0.0),
                (4.7, 0.0, 0.0),
                (2.1, 0.0, 0.0),
            ),
        ),
        (
            "skinny upper cap",
            (
                (0.0, 0.0, 0.0),
                (0.3, 1.4, 0.0),
                (1.3, 2.75, 0.0),
                (3.0, 3.45, 0.0),
                (5.4, 3.55, 0.0),
                (7.9, 3.1, 0.0),
                (9.4, 1.8, 0.0),
                (10.0, 0.0, 0.0),
            ),
        ),
    )
    return tuple(
        (
            name,
            polygon_mesh_from_points(points),
            pizza_triangulate_mesh(polygon_mesh_from_points(points)),
        )
        for name, points in examples
    )


def polygon_mesh_from_points(points: Sequence[Point3]) -> Mesh3:
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in points)
    face = tuple(range(len(vertices)))
    return Mesh3(vertices, (face,), tuple((index, (index + 1) % len(vertices)) for index in face))


def build_example_scene(examples: Sequence[tuple[str, Mesh3, Mesh3]]) -> Scene:
    scene = Scene(
        "pizza_triangulate_examples",
        camera=Camera.orthographic(
            position=(5.0, 0.0, 18.0),
            target=(5.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=12.0,
        ),
    )
    input_style = DisplayStyle(color=(0.08, 0.18, 0.26), render_mode="wireframe")
    output_style = DisplayStyle(color=(0.35, 0.64, 0.54), opacity=0.82)
    for index, (name, polygon, triangulated) in enumerate(examples):
        offset = (index - (len(examples) - 1) / 2.0) * 6.0
        scene = scene.add(
            polygon.translate((0.0, offset, 0.0)),
            name=f"{name} input polygon",
            style=input_style,
        )
        scene = scene.add(
            triangulated.translate((0.0, offset, 0.04)),
            name=f"{name} reduced pizza triangulation",
            style=output_style,
        )
    return scene


def example_summary(examples: Sequence[tuple[str, Mesh3, Mesh3]]) -> str:
    lines = [f"pizza triangulate examples, target min angle {PIZZA_MIN_ANGLE_DEGREES:g} deg"]
    for name, polygon, triangulated in examples:
        lines.append(
            f"{name}: {len(polygon.vertices)} outer vertices -> "
            f"{len(triangulated.vertices)} vertices, {len(triangulated.faces)} triangles, "
            f"worst angle {_mesh_min_angle_degrees(triangulated):.3g} deg"
        )
    return "\n".join(lines)


def _mesh_min_angle_degrees(mesh: Mesh3) -> float:
    if not mesh.faces:
        return 0.0
    V = np.asarray(mesh.vertices, dtype=np.float64)
    return _min_triangle_angle(V, mesh.faces)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show reduced-inner-polygon pizza triangulation examples.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print example summaries without opening a viewer.",
    )
    args = parser.parse_args()

    examples = example_meshes()
    print(example_summary(examples))
    if not args.no_view:
        build_example_scene(examples).view(title="pizza triangulate examples")


if __name__ == "__main__":
    main()
