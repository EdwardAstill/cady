# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false
# pyright: reportUnknownVariableType=false
"""Pizza-web polygon triangulation."""

import numpy as np

SUPPORTED_CONSTRAINTS = frozenset(
    (
        "tolerance",
        "min_angle_degrees",
        "max_inner_rings",
        "max_split_depth",
    )
)

_DEFAULT_MIN_ANGLE_DEGREES = 15.0
_INNER_RING_START_SCALE = 0.12
_INNER_RING_SCALE_STEP = 0.04
_INNER_RING_MAX_SCALE = 0.58
_MIN_SPLIT_AREA_RATIO = 0.08


def pizza_web_triangulate(
    nodes,
    edges,
    *,
    tolerance=1e-9,
    min_angle_degrees=None,
    max_inner_rings=3,
    max_split_depth=8,
):
    """Triangulate closed 2D edge loops with center fills and inner rings."""
    tolerance = _positive_number(tolerance, "tolerance")
    explicit_min_angle = min_angle_degrees is not None
    min_angle_degrees = (
        _DEFAULT_MIN_ANGLE_DEGREES
        if min_angle_degrees is None
        else _min_angle(min_angle_degrees)
    )
    max_inner_rings = _non_negative_int(max_inner_rings, "max_inner_rings")
    max_split_depth = _non_negative_int(max_split_depth, "max_split_depth")

    nodes_in = _coerce_nodes(nodes)
    edges_in = _coerce_edges(edges)
    _validate_edge_indices(nodes_in, edges_in)

    new_vertices = [np.array(node, dtype=np.float64, copy=True).tolist() for node in nodes_in]
    faces = []
    for loop in _edge_loops(edges_in):
        ids = list(loop)
        if _signed_area(np.asarray(new_vertices, dtype=np.float64), ids) < 0.0:
            ids.reverse()
        if len(ids) == 3:
            faces.append(ids)
        elif len(ids) == 4:
            faces.extend(_split_quad(np.asarray(new_vertices, dtype=np.float64), ids))
        else:
            faces.extend(
                _triangulate_ngon(
                    ids,
                    new_vertices,
                    min_angle_degrees=min_angle_degrees,
                    max_inner_rings=max_inner_rings,
                    max_split_depth=max_split_depth,
                    split_depth=0,
                )
            )

    vertices = np.asarray(new_vertices, dtype=np.float64)
    oriented_faces = [
        _ccw_face(vertices, face)
        for face in faces
        if _triangle_area(vertices, face) > tolerance * tolerance
    ]
    if explicit_min_angle:
        _validate_min_angle(vertices, oriented_faces, min_angle_degrees, tolerance)
    face_array = _face_array(oriented_faces)
    return vertices, _add_internal_edges(edges_in, face_array), face_array


def _positive_number(value, name):
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value


def _min_angle(value):
    value = float(value)
    if not np.isfinite(value) or value <= 0.0 or value >= 60.0:
        raise ValueError("min_angle_degrees must be between 0 and 60")
    return value


def _non_negative_int(value, name):
    integer = int(value)
    if integer != value or integer < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return integer


def _coerce_nodes(value):
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("nodes must have shape (n, 2)")
    if not np.all(np.isfinite(array)):
        raise ValueError("nodes must contain only finite values")
    return np.array(array, dtype=np.float64, copy=True)


def _coerce_edges(value):
    array = np.asarray(value, dtype=np.int64)
    if array.size == 0:
        return np.empty((0, 2), dtype=np.int64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("edges must have shape (n, 2)")
    return np.array(array, dtype=np.int64, copy=True)


def _validate_edge_indices(nodes, edges):
    if len(edges) == 0:
        return
    if np.min(edges) < 0 or np.max(edges) >= len(nodes):
        raise ValueError("edges reference nodes outside the node array")


def _edge_loops(edges):
    if len(edges) == 0:
        return ()

    neighbours = {}
    unused_edges = set()
    for start_raw, end_raw in edges:
        start = int(start_raw)
        end = int(end_raw)
        if start == end:
            continue
        edge = _edge_key(start, end)
        if edge in unused_edges:
            continue
        unused_edges.add(edge)
        neighbours.setdefault(start, set()).add(end)
        neighbours.setdefault(end, set()).add(start)

    if any(len(values) != 2 for values in neighbours.values()):
        raise ValueError("edges must form closed loops")

    loops = []
    while unused_edges:
        start, second = next(iter(unused_edges))
        unused_edges.remove((start, second))
        loop = [start, second]
        previous = start
        current = second

        while current != start:
            candidates = [
                candidate
                for candidate in neighbours[current]
                if _edge_key(current, candidate) in unused_edges and candidate != previous
            ]
            if not candidates:
                raise ValueError("edges must form closed loops")
            following = candidates[0]
            unused_edges.remove(_edge_key(current, following))
            loop.append(following)
            previous, current = current, following

        if loop[-1] == start:
            loop.pop()
        if len(loop) < 3:
            raise ValueError("edge loops must contain at least three nodes")
        loops.append(tuple(loop))

    return tuple(loops)


def _triangulate_ngon(
    ids,
    new_vertices,
    *,
    min_angle_degrees,
    max_inner_rings,
    max_split_depth,
    split_depth,
):
    trial_vertices = [list(vertex) for vertex in new_vertices]
    final_faces = _fan_ids_to_centroid(ids, trial_vertices)
    final_angle = _min_triangle_angle(np.asarray(trial_vertices, dtype=np.float64), final_faces)
    if final_angle + 1e-9 >= min_angle_degrees:
        new_vertices[:] = trial_vertices
        return final_faces

    if len(ids) <= 4:
        return _fan_ids_to_centroid(ids, new_vertices)

    ring_vertices = [list(vertex) for vertex in new_vertices]
    ring_faces = _try_inner_rings(
        ids,
        ring_vertices,
        min_angle_degrees=min_angle_degrees,
        max_inner_rings=max_inner_rings,
    )
    ring_angle = _min_triangle_angle(np.asarray(ring_vertices, dtype=np.float64), ring_faces)
    if ring_angle + 1e-9 >= min_angle_degrees:
        new_vertices[:] = ring_vertices
        return ring_faces

    if split_depth < max_split_depth:
        split = _best_chord_split(np.asarray(new_vertices, dtype=np.float64), ids)
        if split is not None:
            first, second = _split_polygon_with_midpoint(ids, *split, new_vertices)
            return [
                *_triangulate_child_polygon(
                    first,
                    new_vertices,
                    min_angle_degrees=min_angle_degrees,
                    max_inner_rings=max_inner_rings,
                    max_split_depth=max_split_depth,
                    split_depth=split_depth + 1,
                ),
                *_triangulate_child_polygon(
                    second,
                    new_vertices,
                    min_angle_degrees=min_angle_degrees,
                    max_inner_rings=max_inner_rings,
                    max_split_depth=max_split_depth,
                    split_depth=split_depth + 1,
                ),
            ]

    new_vertices[:] = ring_vertices
    return ring_faces


def _triangulate_child_polygon(
    ids,
    new_vertices,
    *,
    min_angle_degrees,
    max_inner_rings,
    max_split_depth,
    split_depth,
):
    if len(ids) < 3:
        return []
    if len(ids) == 3:
        return [ids]
    if len(ids) == 4:
        return _split_quad(np.asarray(new_vertices, dtype=np.float64), ids)
    return _triangulate_ngon(
        ids,
        new_vertices,
        min_angle_degrees=min_angle_degrees,
        max_inner_rings=max_inner_rings,
        max_split_depth=max_split_depth,
        split_depth=split_depth,
    )


def _try_inner_rings(ids, new_vertices, *, min_angle_degrees, max_inner_rings):
    best_vertices = [list(vertex) for vertex in new_vertices]
    best_faces = _fan_ids_to_centroid(ids, best_vertices)
    best_angle = _min_triangle_angle(np.asarray(best_vertices, dtype=np.float64), best_faces)

    trial_vertices = [list(vertex) for vertex in new_vertices]
    current_ids = list(ids)
    ring_faces = []

    for _ in range(max_inner_rings):
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
        if final_angle + 1e-9 >= min_angle_degrees:
            new_vertices[:] = final_vertices
            return final_faces

    new_vertices[:] = best_vertices
    return best_faces


def _next_inner_ring(vertices, ids):
    inner_count = _inner_polygon_vertex_count(len(ids))
    if inner_count >= len(ids):
        return None

    best_points = None
    best_faces = []
    best_angle = -1.0

    for inner_points in _scaled_inner_rings(vertices, ids, inner_count):
        trial_vertices = [list(vertex) for vertex in vertices.tolist()]
        faces = _band_faces_to_inner_polygon(ids, inner_points, trial_vertices)
        angle = _min_triangle_angle(np.asarray(trial_vertices, dtype=np.float64), faces)
        if angle > best_angle:
            best_angle = angle
            best_points = inner_points
            best_faces = faces

    if best_points is None:
        return None
    return best_points, best_faces


def _scaled_inner_rings(vertices, ids, inner_count):
    center = np.mean(vertices[np.asarray(ids, dtype=np.int64)], axis=0)
    groups = _outer_index_groups(len(ids), inner_count)
    directions = tuple(_group_direction(vertices, ids, group, center) for group in groups)
    boundary_distances = tuple(
        _ray_boundary_distance(vertices, ids, center, direction) for direction in directions
    )

    rings = []
    scale = _INNER_RING_START_SCALE
    while scale <= _INNER_RING_MAX_SCALE + 1e-12:
        rings.append(
            tuple(
                center + direction * boundary_distance * scale
                for direction, boundary_distance in zip(
                    directions,
                    boundary_distances,
                    strict=True,
                )
            )
        )
        scale += _INNER_RING_SCALE_STEP
    return tuple(rings)


def _inner_polygon_vertex_count(outer_count):
    if outer_count <= 5:
        return 3
    target = int(round(outer_count * 0.45))
    return max(3, min(outer_count - 1, target))


def _outer_index_groups(outer_count, inner_count):
    groups = []
    for index in range(inner_count):
        start = round(index * outer_count / inner_count)
        end = round((index + 1) * outer_count / inner_count)
        groups.append(tuple(range(start, max(start + 1, end))))
    groups[-1] = tuple(range(groups[-1][0], outer_count))
    return tuple(groups)


def _group_direction(vertices, ids, group, center):
    group_points = vertices[np.asarray([ids[index % len(ids)] for index in group], dtype=np.int64)]
    direction = np.mean(group_points, axis=0) - center
    length = float(np.linalg.norm(direction))
    if length <= 0.0:
        angle = 2.0 * np.pi * group[0] / len(ids)
        return np.asarray((float(np.cos(angle)), float(np.sin(angle))), dtype=np.float64)
    return direction / length


def _ray_boundary_distance(vertices, ids, center, direction):
    distances = [
        _ray_segment_distance(
            center,
            direction,
            vertices[ids[index]],
            vertices[ids[(index + 1) % len(ids)]],
        )
        for index in range(len(ids))
    ]
    positive = [distance for distance in distances if distance is not None and distance > 0.0]
    if positive:
        return min(positive)
    fallback = max(float(np.linalg.norm(vertices[index] - center)) for index in ids)
    return fallback if fallback > 0.0 else 1.0


def _ray_segment_distance(origin, direction, start, end):
    segment = end - start
    determinant = -direction[0] * segment[1] + direction[1] * segment[0]
    if abs(float(determinant)) <= 1e-18:
        return None
    diff = start - origin
    distance = (-diff[0] * segment[1] + diff[1] * segment[0]) / determinant
    ratio = (direction[0] * diff[1] - direction[1] * diff[0]) / determinant
    distance = float(distance)
    ratio = float(ratio)
    if distance <= 0.0 or ratio < -1e-9 or ratio > 1.0 + 1e-9:
        return None
    return distance


def _band_faces_to_inner_polygon(ids, inner_points, new_vertices):
    inner_start = len(new_vertices)
    for point in inner_points:
        new_vertices.append(point.tolist())

    outer_count = len(ids)
    inner_count = len(inner_points)
    sector_by_outer_index = tuple(
        min(inner_count - 1, int(index * inner_count / outer_count))
        for index in range(outer_count)
    )

    faces = []
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


def _best_chord_split(vertices, ids):
    if len(ids) < 6:
        return None

    points = tuple((float(vertices[index][0]), float(vertices[index][1])) for index in ids)
    best_split = None
    best_score = -1.0

    for start in range(len(ids)):
        for end in range(start + 2, len(ids)):
            if start == 0 and end == len(ids) - 1:
                continue
            if not _is_valid_chord(points, start, end):
                continue

            first = ids[start : end + 1]
            second = [*ids[end:], *ids[: start + 1]]
            score = _split_compactness_score(vertices, first, second)
            if score is None:
                continue
            if score > best_score:
                best_score = score
                best_split = (start, end)

    return best_split


def _split_polygon_with_midpoint(ids, start, end, new_vertices):
    first_id = ids[start]
    second_id = ids[end]
    midpoint = [
        (new_vertices[first_id][axis] + new_vertices[second_id][axis]) * 0.5
        for axis in range(2)
    ]
    midpoint_id = len(new_vertices)
    new_vertices.append(midpoint)

    return (
        [*ids[start : end + 1], midpoint_id],
        [*ids[end:], *ids[: start + 1], midpoint_id],
    )


def _is_valid_chord(points, start, end):
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


def _segments_intersect(a, b, c, d):
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


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_on_segment(point, start, end):
    return (
        abs(_orientation(start, end, point)) <= 1e-9
        and min(start[0], end[0]) - 1e-9 <= point[0] <= max(start[0], end[0]) + 1e-9
        and min(start[1], end[1]) - 1e-9 <= point[1] <= max(start[1], end[1]) + 1e-9
    )


def _point_in_polygon(point, polygon):
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


def _split_compactness_score(vertices, first, second):
    first_area = _polygon_area(vertices, first)
    second_area = _polygon_area(vertices, second)
    larger_area = max(first_area, second_area)
    if larger_area <= 1e-12:
        return None
    if min(first_area, second_area) / larger_area < _MIN_SPLIT_AREA_RATIO:
        return None

    first_quality = _polygon_compactness(vertices, first)
    second_quality = _polygon_compactness(vertices, second)
    worst_quality = min(first_quality, second_quality)
    average_quality = (first_quality + second_quality) * 0.5
    return 0.8 * worst_quality + 0.2 * average_quality


def _polygon_compactness(vertices, ids):
    area = _polygon_area(vertices, ids)
    perimeter = _polygon_perimeter(vertices, ids)
    if perimeter <= 1e-12:
        return 0.0
    return 4.0 * np.pi * area / (perimeter * perimeter)


def _polygon_area(vertices, ids):
    return abs(_signed_area(vertices, ids))


def _polygon_perimeter(vertices, ids):
    return sum(
        float(np.linalg.norm(vertices[ids[index]] - vertices[ids[(index + 1) % len(ids)]]))
        for index in range(len(ids))
    )


def _fan_ids_to_centroid(ids, new_vertices):
    if len(ids) < 3:
        return []
    if len(ids) == 3:
        return [list(ids)]
    return _fan_from_centroid(np.asarray(new_vertices, dtype=np.float64), ids, new_vertices)


def _fan_from_centroid(vertices, ids, new_vertices):
    centroid_index = len(new_vertices)
    centroid = np.mean(vertices[np.asarray(ids, dtype=np.int64)], axis=0).tolist()
    new_vertices.append(centroid)

    faces = []
    for index in range(len(ids)):
        faces.append([ids[index], ids[(index + 1) % len(ids)], centroid_index])
    return faces


def _split_quad(vertices, ids):
    a, b, c, d = ids
    diag_ac = float(np.linalg.norm(vertices[c] - vertices[a]))
    diag_bd = float(np.linalg.norm(vertices[d] - vertices[b]))

    if diag_ac <= diag_bd:
        return [[a, b, c], [a, c, d]]
    return [[a, b, d], [b, c, d]]


def _face_array(faces):
    if not faces:
        return np.empty((0, 3), dtype=np.int64)
    return np.asarray(faces, dtype=np.int64)


def _add_internal_edges(edges, faces):
    edge_set = _edge_key_set(edges)
    for a, b, c in faces:
        edge_set.add(_edge_key(int(a), int(b)))
        edge_set.add(_edge_key(int(b), int(c)))
        edge_set.add(_edge_key(int(c), int(a)))
    if not edge_set:
        return np.empty((0, 2), dtype=np.int64)
    return np.asarray(sorted(edge_set), dtype=np.int64)


def _edge_key_set(edges):
    return {
        _edge_key(int(start), int(end))
        for start, end in edges
        if int(start) != int(end)
    }


def _edge_key(start, end):
    return (start, end) if start < end else (end, start)


def _ccw_face(vertices, face):
    a, b, c = (int(index) for index in face)
    if _cross(vertices[a], vertices[b], vertices[c]) < 0.0:
        return (a, c, b)
    return (a, b, c)


def _signed_area(vertices, ids):
    return 0.5 * sum(
        float(vertices[start, 0] * vertices[end, 1] - vertices[end, 0] * vertices[start, 1])
        for start, end in zip(ids, ids[1:] + ids[:1], strict=True)
    )


def _cross(a, b, c):
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _triangle_area(vertices, face):
    a, b, c = (int(index) for index in face)
    return 0.5 * abs(_cross(vertices[a], vertices[b], vertices[c]))


def _min_triangle_angle(vertices, faces):
    if not faces:
        return 0.0
    return min(_triangle_min_angle(vertices, face) for face in faces)


def _triangle_min_angle(vertices, face):
    a, b, c = (int(index) for index in face)
    ab = float(np.linalg.norm(vertices[a] - vertices[b]))
    bc = float(np.linalg.norm(vertices[b] - vertices[c]))
    ca = float(np.linalg.norm(vertices[c] - vertices[a]))
    return min(
        _angle_degrees(ab, ca, bc),
        _angle_degrees(ab, bc, ca),
        _angle_degrees(bc, ca, ab),
    )


def _angle_degrees(first, second, opposite):
    denominator = 2.0 * first * second
    if denominator <= 0.0:
        return 0.0
    cosine = (first * first + second * second - opposite * opposite) / denominator
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, cosine)))))


def _validate_min_angle(vertices, faces, min_angle_degrees, tolerance):
    worst_angle = None
    for face in faces:
        if _triangle_area(vertices, face) <= tolerance * tolerance:
            continue
        angle = _triangle_min_angle(vertices, face)
        if angle + 1e-9 >= min_angle_degrees:
            continue
        worst_angle = angle if worst_angle is None else min(worst_angle, angle)
    if worst_angle is not None:
        raise ValueError(
            "triangulation produced a triangle angle "
            f"{worst_angle:.6g} below min_angle_degrees {min_angle_degrees:.6g}"
        )
