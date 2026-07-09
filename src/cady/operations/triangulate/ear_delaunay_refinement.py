# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false
# pyright: reportUnknownVariableType=false
"""Ear clipping with constrained Delaunay flips and optional refinement."""

import numpy as np

SUPPORTED_CONSTRAINTS = frozenset(
    (
        "tolerance",
        "target_edge_length",
        "max_edge_length",
        "max_area",
        "min_angle_degrees",
    )
)


def ear_delaunay_refinement_triangulate(
    nodes,
    edges,
    *,
    tolerance=1e-9,
    target_edge_length=None,
    max_edge_length=None,
    max_area=None,
    min_angle_degrees=None,
):
    """Triangulate closed 2D edge loops."""
    tolerance = _positive_number(tolerance, "tolerance")
    target_edge_length = _optional_positive_number(target_edge_length, "target_edge_length")
    max_edge_length = _optional_positive_number(max_edge_length, "max_edge_length")
    max_area = _optional_positive_number(max_area, "max_area")
    min_angle_degrees = _optional_min_angle(min_angle_degrees)

    nodes_out = _coerce_nodes(nodes)
    edges_out = _coerce_edges(edges)
    _validate_edge_indices(nodes_out, edges_out)

    edge_limit = _edge_length_limit(target_edge_length, max_edge_length)
    nodes_out, boundary_edges = _refine_edges(nodes_out, edges_out, edge_limit)
    faces = []
    protected_edges = _edge_key_set(boundary_edges)

    for loop in _edge_loops(boundary_edges):
        if edge_limit is not None or max_area is not None:
            nodes_out, loop_faces = _triangulate_seeded_loop2(nodes_out, loop, tolerance)
        else:
            loop_faces = _triangulate_loop2(nodes_out, loop, tolerance)
            loop_faces = _constrained_delaunay_faces(
                nodes_out,
                loop_faces,
                protected_edges=protected_edges,
                tolerance=tolerance,
            )
        nodes_out, loop_faces = _refine_triangle_mesh(
            nodes_out,
            loop_faces,
            protected_edges=protected_edges,
            tolerance=tolerance,
            edge_limit=edge_limit,
            max_area=max_area,
            min_angle_degrees=min_angle_degrees,
        )
        faces.extend(loop_faces)

    face_array = _face_array(faces)
    return nodes_out, _add_internal_edges(boundary_edges, face_array), face_array


def _positive_number(value, name):
    value = float(value)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value


def _optional_positive_number(value, name):
    if value is None:
        return None
    return _positive_number(value, name)


def _optional_min_angle(value):
    if value is None:
        return None
    value = float(value)
    if not np.isfinite(value) or value <= 0.0 or value >= 60.0:
        raise ValueError("min_angle_degrees must be between 0 and 60")
    return value


def _edge_length_limit(target_edge_length, max_edge_length):
    values = [value for value in (target_edge_length, max_edge_length) if value is not None]
    return min(values) if values else None


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


def _refine_edges(nodes, edges, max_length):
    if max_length is None or len(edges) == 0:
        return nodes, edges

    vertices = [np.array(node, dtype=np.float64, copy=True) for node in nodes]
    refined_edges = []
    for start_raw, end_raw in edges:
        start = int(start_raw)
        end = int(end_raw)
        length = float(np.linalg.norm(nodes[end] - nodes[start]))
        segments = max(1, int(np.ceil(length / max_length)))
        previous = start
        for segment in range(1, segments):
            ratio = segment / segments
            point = nodes[start] + (nodes[end] - nodes[start]) * ratio
            current = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))
            refined_edges.append((previous, current))
            previous = current
        refined_edges.append((previous, end))
    return np.asarray(vertices, dtype=np.float64), np.asarray(refined_edges, dtype=np.int64)


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


def _refine_triangle_mesh(
    nodes,
    faces,
    *,
    protected_edges,
    tolerance,
    edge_limit,
    max_area,
    min_angle_degrees,
):
    if (edge_limit is None and max_area is None) or not faces:
        _validate_min_triangle_angle(
            nodes,
            faces,
            min_angle_degrees=min_angle_degrees,
            tolerance=tolerance,
        )
        return nodes, faces

    vertices = [np.array(node, dtype=np.float64, copy=True) for node in nodes]
    refined = _constrained_delaunay_faces(
        np.asarray(vertices, dtype=np.float64),
        list(faces),
        protected_edges=protected_edges,
        tolerance=tolerance,
    )
    min_area = tolerance * tolerance

    for _ in range(64):
        nodes_array = np.asarray(vertices, dtype=np.float64)
        edge_splits = {}
        centroid_faces = set()
        for face in refined:
            split = _next_refinement_split(
                nodes_array,
                face,
                protected_edges=protected_edges,
                tolerance=tolerance,
                edge_limit=edge_limit,
                max_area=max_area,
                min_angle_degrees=min_angle_degrees,
            )
            if split is None:
                continue
            if split[0] == "edge":
                edge_splits.setdefault(split[1], -1)
            else:
                centroid_faces.add(split[1])

        if not edge_splits and not centroid_faces:
            break

        for edge in edge_splits:
            start, end = edge
            point = 0.5 * (vertices[start] + vertices[end])
            edge_splits[edge] = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))

        centroid_by_face = {}
        for face in centroid_faces:
            point = (vertices[face[0]] + vertices[face[1]] + vertices[face[2]]) / 3.0
            centroid_by_face[face] = len(vertices)
            vertices.append(np.array(point, dtype=np.float64, copy=True))

        split_nodes = np.asarray(vertices, dtype=np.float64)
        next_faces = []
        for face in refined:
            selected_edges = [edge for edge in _face_edges(face) if edge in edge_splits]
            if selected_edges:
                children = [face]
                for edge in selected_edges:
                    children = _split_faces_on_edge(
                        children,
                        edge,
                        edge_splits[edge],
                        split_nodes,
                        min_area=min_area,
                    )
                next_faces.extend(children)
                continue

            centroid = centroid_by_face.get(face)
            if centroid is not None:
                next_faces.extend(
                    _split_face_at_point(
                        face,
                        centroid,
                        split_nodes,
                        min_area=min_area,
                    )
                )
                continue

            next_faces.append(face)

        refined = _constrained_delaunay_faces(
            np.asarray(vertices, dtype=np.float64),
            next_faces,
            protected_edges=protected_edges,
            tolerance=tolerance,
        )

    nodes_out = np.asarray(vertices, dtype=np.float64)
    _validate_min_triangle_angle(
        nodes_out,
        refined,
        min_angle_degrees=min_angle_degrees,
        tolerance=tolerance,
    )
    return nodes_out, refined


def _next_refinement_split(
    nodes,
    face,
    *,
    protected_edges,
    tolerance,
    edge_limit,
    max_area,
    min_angle_degrees,
):
    lengths = _face_edge_lengths(nodes, face)
    area = _triangle_area(nodes, face)
    if area <= tolerance * tolerance:
        return None

    score = 1.0
    if edge_limit is not None:
        score = max(score, max(lengths) / edge_limit)
    if max_area is not None:
        score = max(score, float(np.sqrt(area / max_area)))
    if min_angle_degrees is not None:
        min_angle = _min_angle_degrees(lengths)
        if min_angle > 0.0:
            score = max(score, min_angle_degrees / min_angle)
    if score <= 1.0 + 1e-12:
        return None

    candidate_edges = [
        edge
        for _length, edge in sorted(zip(lengths, _face_edges(face), strict=True), reverse=True)
        if edge not in protected_edges
    ]
    if candidate_edges:
        return ("edge", candidate_edges[0])
    return ("centroid", face)


def _validate_min_triangle_angle(nodes, faces, *, min_angle_degrees, tolerance):
    if min_angle_degrees is None:
        return

    min_area = tolerance * tolerance
    worst_angle = None
    for face in faces:
        if _triangle_area(nodes, face) <= min_area:
            continue
        angle = _min_angle_degrees(_face_edge_lengths(nodes, face))
        if angle + 1e-9 >= min_angle_degrees:
            continue
        worst_angle = angle if worst_angle is None else min(worst_angle, angle)

    if worst_angle is not None:
        raise ValueError(
            "triangulation produced a triangle angle "
            f"{worst_angle:.6g} below min_angle_degrees {min_angle_degrees:.6g}"
        )


def _split_faces_on_edge(faces, edge, midpoint, nodes, *, min_area):
    refined = []
    edge_key = _edge_key(*edge)
    for face in faces:
        if edge_key not in _face_edges(face):
            refined.append(face)
            continue
        for child in _split_face_on_edge(face, edge_key, midpoint):
            if _triangle_area(nodes, child) > min_area:
                refined.append(_ccw_face2(nodes, child))
    return refined


def _split_face_on_edge(face, edge, midpoint):
    for position in range(3):
        start = face[position]
        end = face[(position + 1) % 3]
        other = face[(position + 2) % 3]
        if _edge_key(start, end) == edge:
            return (start, midpoint, other), (midpoint, end, other)
    raise ValueError("face does not contain split edge")


def _split_face_at_point(face, point, nodes, *, min_area):
    refined = []
    a, b, c = face
    for child in ((a, b, point), (b, c, point), (c, a, point)):
        if _triangle_area(nodes, child) > min_area:
            refined.append(_ccw_face2(nodes, child))
    return refined


def _constrained_delaunay_faces(nodes, faces, *, protected_edges, tolerance):
    if len(faces) < 2:
        return [_ccw_face2(nodes, face) for face in faces]

    refined = [_ccw_face2(nodes, face) for face in faces]
    max_iterations = max(1, len(refined) * len(refined))
    for _ in range(max_iterations):
        edge_faces = _interior_edge_faces(refined, protected_edges)
        flipped = False
        for edge, adjacent in edge_faces.items():
            if len(adjacent) != 2:
                continue

            left_index, right_index = adjacent
            left = refined[left_index]
            right = refined[right_index]
            a, b = edge
            c = _opposite_vertex(left, edge)
            d = _opposite_vertex(right, edge)
            if c is None or d is None or c == d:
                continue
            if not _is_convex_quad2(nodes, a, b, c, d, tolerance):
                continue
            if not _point_in_circumcircle2(nodes[a], nodes[b], nodes[c], nodes[d], tolerance):
                continue

            first = _ccw_face2(nodes, (c, d, a))
            second = _ccw_face2(nodes, (d, c, b))
            if _triangle_area(nodes, first) <= tolerance * tolerance:
                continue
            if _triangle_area(nodes, second) <= tolerance * tolerance:
                continue
            refined[left_index] = first
            refined[right_index] = second
            flipped = True
            break

        if not flipped:
            break

    return refined


def _interior_edge_faces(faces, protected_edges):
    edge_faces = {}
    for index, face in enumerate(faces):
        for edge in _face_edges(face):
            if edge in protected_edges:
                continue
            edge_faces.setdefault(edge, []).append(index)
    return edge_faces


def _opposite_vertex(face, edge):
    a, b = edge
    for index in face:
        if index != a and index != b:
            return index
    return None


def _is_convex_quad2(nodes, a, b, c, d, tolerance):
    edge_side_c = _cross2(nodes[a], nodes[b], nodes[c])
    edge_side_d = _cross2(nodes[a], nodes[b], nodes[d])
    new_edge_side_a = _cross2(nodes[c], nodes[d], nodes[a])
    new_edge_side_b = _cross2(nodes[c], nodes[d], nodes[b])
    limit = tolerance * tolerance
    return edge_side_c * edge_side_d < -limit and new_edge_side_a * new_edge_side_b < -limit


def _point_in_circumcircle2(a, b, c, point, tolerance):
    ax = float(a[0] - point[0])
    ay = float(a[1] - point[1])
    bx = float(b[0] - point[0])
    by = float(b[1] - point[1])
    cx = float(c[0] - point[0])
    cy = float(c[1] - point[1])
    determinant = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    orientation = _cross2(a, b, c)
    if orientation < 0.0:
        determinant = -determinant
    return determinant > tolerance * tolerance


def _triangulate_seeded_loop2(nodes, loop, tolerance):
    indices = list(loop)
    if len(indices) < 3:
        return nodes, []
    if _signed_area2(nodes, indices) < 0.0:
        indices.reverse()

    seed = _interior_seed2(nodes, indices, tolerance)
    if seed is None or not _seed_sees_loop2(nodes, indices, seed, tolerance):
        return nodes, _triangulate_loop2(nodes, tuple(indices), tolerance)

    seed_index = len(nodes)
    seeded_nodes = np.vstack((nodes, seed)).astype(np.float64)
    faces = []
    for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
        face = (start, end, seed_index)
        if _triangle_area(seeded_nodes, face) > tolerance * tolerance:
            faces.append(face)
    if not faces:
        return nodes, _triangulate_loop2(nodes, tuple(indices), tolerance)
    return seeded_nodes, faces


def _interior_seed2(nodes, indices, tolerance):
    polygon = [nodes[index] for index in indices]
    bounds = np.asarray(polygon, dtype=np.float64)
    lower = np.min(bounds, axis=0)
    upper = np.max(bounds, axis=0)
    span = upper - lower

    candidates = [
        _polygon_centroid2(nodes, indices),
        np.mean(bounds, axis=0),
        (lower + upper) / 2.0,
    ]
    for x_step in range(1, 6):
        for y_step in range(1, 6):
            candidates.append(
                np.array(
                    (
                        lower[0] + span[0] * x_step / 6.0,
                        lower[1] + span[1] * y_step / 6.0,
                    ),
                    dtype=np.float64,
                )
            )

    best = None
    best_distance = tolerance
    center = (lower + upper) / 2.0
    best_center_distance = float("inf")
    for candidate in candidates:
        if not _point_in_loop2(candidate, nodes, indices, tolerance):
            continue
        boundary_distance = _distance_to_loop2(candidate, nodes, indices)
        center_distance = float(np.linalg.norm(candidate - center))
        if (
            boundary_distance > best_distance
            or abs(boundary_distance - best_distance) <= tolerance
            and center_distance < best_center_distance
        ):
            best = candidate
            best_distance = boundary_distance
            best_center_distance = center_distance
    return best


def _polygon_centroid2(nodes, indices):
    area_sum = 0.0
    x_sum = 0.0
    y_sum = 0.0
    for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
        cross = float(nodes[start, 0] * nodes[end, 1] - nodes[end, 0] * nodes[start, 1])
        area_sum += cross
        x_sum += float(nodes[start, 0] + nodes[end, 0]) * cross
        y_sum += float(nodes[start, 1] + nodes[end, 1]) * cross
    if abs(area_sum) <= 1e-18:
        return np.mean(nodes[indices], axis=0)
    return np.array((x_sum / (3.0 * area_sum), y_sum / (3.0 * area_sum)), dtype=np.float64)


def _seed_sees_loop2(nodes, indices, seed, tolerance):
    for vertex_position, vertex in enumerate(indices):
        if not _segment_stays_in_loop2(
            seed,
            nodes[vertex],
            vertex_position,
            nodes,
            indices,
            tolerance,
        ):
            return False
    return True


def _segment_stays_in_loop2(start, end, end_position, nodes, indices, tolerance):
    for fraction in (0.25, 0.5, 0.75):
        point = start + (end - start) * fraction
        if not _point_in_loop2(point, nodes, indices, tolerance):
            return False

    end_vertex = indices[end_position]
    adjacent = {end_vertex, indices[end_position - 1], indices[(end_position + 1) % len(indices)]}
    for edge_start, edge_end in zip(indices, indices[1:] + indices[:1], strict=True):
        if edge_start in adjacent and edge_end in adjacent:
            continue
        if _segments_intersect2(start, end, nodes[edge_start], nodes[edge_end], tolerance):
            return False
    return True


def _point_in_loop2(point, nodes, indices, tolerance):
    inside = False
    previous = indices[-1]
    for current in indices:
        a = nodes[current]
        b = nodes[previous]
        if _point_on_segment2(point, a, b, tolerance):
            return False
        if ((a[1] > point[1]) != (b[1] > point[1])) and (
            point[0] < (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]) + a[0]
        ):
            inside = not inside
        previous = current
    return inside


def _distance_to_loop2(point, nodes, indices):
    return min(
        _distance_to_segment2(point, nodes[start], nodes[end])
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True)
    )


def _distance_to_segment2(point, start, end):
    segment = end - start
    length_squared = float(np.dot(segment, segment))
    if length_squared == 0.0:
        return float(np.linalg.norm(point - start))
    ratio = max(0.0, min(1.0, float(np.dot(point - start, segment)) / length_squared))
    closest = start + segment * ratio
    return float(np.linalg.norm(point - closest))


def _point_on_segment2(point, start, end, tolerance):
    return (
        abs(_cross2(start, end, point)) <= tolerance
        and min(start[0], end[0]) - tolerance <= point[0] <= max(start[0], end[0]) + tolerance
        and min(start[1], end[1]) - tolerance <= point[1] <= max(start[1], end[1]) + tolerance
    )


def _segments_intersect2(a, b, c, d, tolerance):
    ab_c = _cross2(a, b, c)
    ab_d = _cross2(a, b, d)
    cd_a = _cross2(c, d, a)
    cd_b = _cross2(c, d, b)
    if ((ab_c > tolerance and ab_d < -tolerance) or (ab_c < -tolerance and ab_d > tolerance)) and (
        (cd_a > tolerance and cd_b < -tolerance) or (cd_a < -tolerance and cd_b > tolerance)
    ):
        return True
    return (
        abs(ab_c) <= tolerance
        and _point_on_segment2(c, a, b, tolerance)
        or abs(ab_d) <= tolerance
        and _point_on_segment2(d, a, b, tolerance)
        or abs(cd_a) <= tolerance
        and _point_on_segment2(a, c, d, tolerance)
        or abs(cd_b) <= tolerance
        and _point_on_segment2(b, c, d, tolerance)
    )


def _triangulate_loop2(nodes, loop, tolerance):
    indices = list(loop)
    if len(indices) < 3:
        return []
    if _signed_area2(nodes, indices) < 0.0:
        indices.reverse()

    faces = []
    guard = len(indices) * len(indices)
    while len(indices) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            if _cross2(nodes[previous], nodes[current], nodes[following]) <= tolerance:
                continue
            if any(
                candidate not in {previous, current, following}
                and _point_in_triangle(
                    nodes[candidate],
                    nodes[previous],
                    nodes[current],
                    nodes[following],
                    tolerance,
                )
                for candidate in indices
            ):
                continue
            faces.append((previous, current, following))
            del indices[position]
            clipped = True
            break
        if clipped:
            continue

        for position, current in enumerate(indices):
            previous = indices[position - 1]
            following = indices[(position + 1) % len(indices)]
            if abs(_cross2(nodes[previous], nodes[current], nodes[following])) <= tolerance:
                del indices[position]
                clipped = True
                break
        if not clipped:
            break

    if (
        len(indices) == 3
        and abs(_cross2(nodes[indices[0]], nodes[indices[1]], nodes[indices[2]])) > tolerance
    ):
        faces.append((indices[0], indices[1], indices[2]))
    return faces


def _signed_area2(nodes, indices):
    return 0.5 * sum(
        float(nodes[start, 0] * nodes[end, 1] - nodes[end, 0] * nodes[start, 1])
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True)
    )


def _cross2(a, b, c):
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _point_in_triangle(point, a, b, c, tolerance):
    return (
        _cross2(a, b, point) >= -tolerance
        and _cross2(b, c, point) >= -tolerance
        and _cross2(c, a, point) >= -tolerance
    )


def _ccw_face2(nodes, face):
    a, b, c = face
    if _cross2(nodes[a], nodes[b], nodes[c]) < 0.0:
        return (a, c, b)
    return face


def _face_edges(face):
    a, b, c = face
    return (_edge_key(a, b), _edge_key(b, c), _edge_key(c, a))


def _face_edge_lengths(nodes, face):
    a, b, c = face
    return (
        float(np.linalg.norm(nodes[a] - nodes[b])),
        float(np.linalg.norm(nodes[b] - nodes[c])),
        float(np.linalg.norm(nodes[c] - nodes[a])),
    )


def _triangle_area(nodes, face):
    a, b, c = face
    ab = nodes[b] - nodes[a]
    ac = nodes[c] - nodes[a]
    return 0.5 * abs(float(ab[0] * ac[1] - ab[1] * ac[0]))


def _min_angle_degrees(lengths):
    ab, bc, ca = lengths
    if ab <= 0.0 or bc <= 0.0 or ca <= 0.0:
        return 0.0
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
    cosine = max(-1.0, min(1.0, cosine))
    return float(np.degrees(np.arccos(cosine)))
