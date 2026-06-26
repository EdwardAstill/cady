from __future__ import annotations

from typing import TypeAlias

from cady.errors import WriteError
from cady.operations.sampling2d import Point2

Triangle2: TypeAlias = tuple[Point2, Point2, Point2]


def dedupe_closed(points: tuple[Point2, ...]) -> tuple[Point2, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        return points[:-1]
    return points


def area2(points: tuple[Point2, ...]) -> float:
    return sum(
        a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1], strict=True)
    ) / 2


def is_self_intersecting(points: tuple[Point2, ...]) -> bool:
    def ccw(a: Point2, b: Point2, c: Point2) -> bool:
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    edges = list(zip(points, points[1:] + points[:1], strict=True))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if abs(i - j) <= 1 or {i, j} == {0, len(edges) - 1}:
                continue
            if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d):
                return True
    return False


def triangulate_polygon(
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...] = (),
    *,
    tolerance: float,
) -> list[Triangle2]:
    outer = dedupe_closed(outer)
    holes = tuple(dedupe_closed(hole) for hole in holes)
    if is_self_intersecting(outer):
        preview = ", ".join(str(point) for point in outer[:3])
        raise WriteError(f"self-intersecting profile near first 3 points: {preview}")
    if not holes:
        return _triangulate_simple_polygon(outer, tolerance=tolerance)
    return _triangulate_polygon_with_holes(outer, holes, tolerance=tolerance)


def _point_in_poly(point: Point2, poly: tuple[Point2, ...]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, pi_ in enumerate(poly):
        pj = poly[j]
        if ((pi_[1] > point[1]) != (pj[1] > point[1])) and (
            point[0] < (pj[0] - pi_[0]) * (point[1] - pi_[1]) / (pj[1] - pi_[1]) + pi_[0]
        ):
            inside = not inside
        j = i
    return inside


def _cross2(a: Point2, b: Point2, c: Point2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _geometry_tolerance(points: tuple[Point2, ...], tolerance: float) -> float:
    span = max(
        max(point[0] for point in points) - min(point[0] for point in points),
        max(point[1] for point in points) - min(point[1] for point in points),
    )
    return max(span * 1e-12, tolerance * 1e-6, 1e-12)


def _same_point(a: Point2, b: Point2, tolerance: float) -> bool:
    return abs(a[0] - b[0]) <= tolerance and abs(a[1] - b[1]) <= tolerance


def _point_on_segment(point: Point2, a: Point2, b: Point2, tolerance: float) -> bool:
    if abs(_cross2(a, b, point)) > tolerance:
        return False
    return (
        min(a[0], b[0]) - tolerance <= point[0] <= max(a[0], b[0]) + tolerance
        and min(a[1], b[1]) - tolerance <= point[1] <= max(a[1], b[1]) + tolerance
    )


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2, tolerance: float) -> bool:
    if (
        max(a[0], b[0]) + tolerance < min(c[0], d[0])
        or max(c[0], d[0]) + tolerance < min(a[0], b[0])
        or max(a[1], b[1]) + tolerance < min(c[1], d[1])
        or max(c[1], d[1]) + tolerance < min(a[1], b[1])
    ):
        return False

    ab_c = _cross2(a, b, c)
    ab_d = _cross2(a, b, d)
    cd_a = _cross2(c, d, a)
    cd_b = _cross2(c, d, b)
    if (
        (ab_c > tolerance and ab_d < -tolerance)
        or (ab_c < -tolerance and ab_d > tolerance)
    ) and (
        (cd_a > tolerance and cd_b < -tolerance)
        or (cd_a < -tolerance and cd_b > tolerance)
    ):
        return True
    return (
        abs(ab_c) <= tolerance
        and _point_on_segment(c, a, b, tolerance)
        or abs(ab_d) <= tolerance
        and _point_on_segment(d, a, b, tolerance)
        or abs(cd_a) <= tolerance
        and _point_on_segment(a, c, d, tolerance)
        or abs(cd_b) <= tolerance
        and _point_on_segment(b, c, d, tolerance)
    )


def _point_in_triangle(point: Point2, a: Point2, b: Point2, c: Point2, tolerance: float) -> bool:
    return (
        _cross2(a, b, point) >= -tolerance
        and _cross2(b, c, point) >= -tolerance
        and _cross2(c, a, point) >= -tolerance
    )


def _clean_ring(points: tuple[Point2, ...]) -> tuple[Point2, ...]:
    clean: list[Point2] = []
    for point in dedupe_closed(points):
        if clean and point == clean[-1]:
            continue
        clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    return tuple(clean)


def _triangulate_simple_polygon(points: tuple[Point2, ...], *, tolerance: float) -> list[Triangle2]:
    points = _clean_ring(points)
    if len(points) < 3:
        return []
    if area2(points) < 0:
        points = tuple(reversed(points))

    eps = _geometry_tolerance(points, tolerance)
    remaining = list(points)
    triangles: list[Triangle2] = []
    guard = len(remaining) * len(remaining)

    while len(remaining) > 3 and guard > 0:
        guard -= 1
        clipped = False
        for index, point in enumerate(remaining):
            previous_index = (index - 1) % len(remaining)
            following_index = (index + 1) % len(remaining)
            previous = remaining[previous_index]
            following = remaining[following_index]
            if _cross2(previous, point, following) <= eps:
                continue
            if any(
                not (
                    candidate_index in {previous_index, index, following_index}
                    or _same_point(candidate, previous, eps)
                    or _same_point(candidate, point, eps)
                    or _same_point(candidate, following, eps)
                )
                and _point_in_triangle(candidate, previous, point, following, eps)
                for candidate_index, candidate in enumerate(remaining)
            ):
                continue
            triangles.append((previous, point, following))
            del remaining[index]
            clipped = True
            break

        if clipped:
            continue

        for index, point in enumerate(remaining):
            previous = remaining[index - 1]
            following = remaining[(index + 1) % len(remaining)]
            if _same_point(point, previous, eps) or abs(_cross2(previous, point, following)) <= eps:
                del remaining[index]
                clipped = True
                break
        if not clipped:
            raise WriteError("could not triangulate polygon profile; check for invalid boundaries")

    if len(remaining) == 3 and abs(_cross2(remaining[0], remaining[1], remaining[2])) > eps:
        triangles.append((remaining[0], remaining[1], remaining[2]))
    return triangles


def _bridge_is_visible(
    start: Point2,
    end: Point2,
    polygon: tuple[Point2, ...],
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...],
    current_hole: int,
    tolerance: float,
) -> bool:
    if _same_point(start, end, tolerance):
        return False

    for fraction in (0.25, 0.5, 0.75):
        sample = (
            start[0] + (end[0] - start[0]) * fraction,
            start[1] + (end[1] - start[1]) * fraction,
        )
        if not _point_in_poly(sample, outer):
            return False
        if any(_point_in_poly(sample, hole) for hole in holes):
            return False

    for a, b in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if _same_point(a, end, tolerance) or _same_point(b, end, tolerance):
            continue
        if _segments_intersect(start, end, a, b, tolerance):
            return False

    for hole_index, hole in enumerate(holes):
        for a, b in zip(hole, hole[1:] + hole[:1], strict=True):
            if hole_index == current_hole and (
                _same_point(a, start, tolerance) or _same_point(b, start, tolerance)
            ):
                continue
            if _segments_intersect(start, end, a, b, tolerance):
                return False
    return True


def _bridge_hole(
    polygon: tuple[Point2, ...],
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...],
    hole_index: int,
    *,
    tolerance: float,
) -> tuple[Point2, ...]:
    hole = holes[hole_index]
    eps = _geometry_tolerance(outer + tuple(point for hole in holes for point in hole), tolerance)
    start_index = max(range(len(hole)), key=lambda index: (hole[index][0], -abs(hole[index][1])))
    start = hole[start_index]
    candidate_indices = list(range(len(polygon)))
    candidate_indices.sort(
        key=lambda index: (
            polygon[index][0] < start[0] - eps,
            (polygon[index][0] - start[0]) ** 2 + (polygon[index][1] - start[1]) ** 2,
        )
    )

    for end_index in candidate_indices:
        end = polygon[end_index]
        if not _bridge_is_visible(start, end, polygon, outer, holes, hole_index, eps):
            continue
        hole_path = hole[start_index:] + hole[:start_index] + (start,)
        return polygon[: end_index + 1] + hole_path + (end,) + polygon[end_index + 1 :]

    raise WriteError("could not connect polygon hole to outer boundary")


def _triangulate_polygon_with_holes(
    outer: tuple[Point2, ...],
    holes: tuple[tuple[Point2, ...], ...],
    *,
    tolerance: float,
) -> list[Triangle2]:
    if area2(outer) < 0:
        outer = tuple(reversed(outer))
    oriented_holes = tuple(tuple(reversed(hole)) if area2(hole) > 0 else hole for hole in holes)
    polygon = outer
    for hole_index in sorted(
        range(len(oriented_holes)),
        key=lambda index: max(point[0] for point in oriented_holes[index]),
        reverse=True,
    ):
        polygon = _bridge_hole(
            polygon,
            outer,
            oriented_holes,
            hole_index,
            tolerance=tolerance,
        )
    return _triangulate_simple_polygon(polygon, tolerance=tolerance)
