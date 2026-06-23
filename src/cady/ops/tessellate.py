from __future__ import annotations

from math import acos, ceil, cos, pi, sin, sqrt
from typing import TypeAlias

from cady.domain.base import AxisString, Shape2D, Shape3D, axis_vector
from cady.domain.shapes2d import Arc, Circle, Line, Path, Polyline, Rectangle, Spline
from cady.domain.shapes3d import Extrusion, Prism, Revolution, Sphere
from cady.domain.vec import Vec2, Vec3
from cady.errors import WriteError

Triangle2: TypeAlias = tuple[Vec2, Vec2, Vec2]
Triangle3: TypeAlias = tuple[Vec3, Vec3, Vec3]


def _segments_for_circle(radius: float, tolerance: float) -> int:
    tolerance = max(float(tolerance), 1e-9)
    if tolerance >= radius:
        return 12
    angle = 2 * acos(max(-1.0, min(1.0, 1 - tolerance / radius)))
    return max(12, ceil((2 * pi) / angle))


def _dedupe_closed(points: list[Vec2]) -> tuple[Vec2, ...]:
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return tuple(points)


def curves_to_polyline(shape: Shape2D, *, tolerance: float) -> Polyline:
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if isinstance(shape, Polyline):
        return shape
    if isinstance(shape, Rectangle):
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(shape.corners(), closed=True, inner_loops=loops)
    if isinstance(shape, Line):
        return Polyline((shape.a, shape.b), closed=False)
    if isinstance(shape, Circle):
        n = _segments_for_circle(shape.radius, tolerance)
        pts = [
            Vec2(
                shape.centre.x + shape.radius * cos(2 * pi * i / n),
                shape.centre.y + shape.radius * sin(2 * pi * i / n),
            )
            for i in range(n)
        ]
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(tuple(pts), closed=True, inner_loops=loops)
    if isinstance(shape, Arc):
        sweep = shape.end_rad - shape.start_rad
        n = max(2, ceil(abs(sweep) / (2 * pi) * _segments_for_circle(shape.radius, tolerance)))
        pts = [
            Vec2(
                shape.centre.x + shape.radius * cos(shape.start_rad + sweep * i / n),
                shape.centre.y + shape.radius * sin(shape.start_rad + sweep * i / n),
            )
            for i in range(n + 1)
        ]
        return Polyline(tuple(pts), closed=False)
    if isinstance(shape, Spline):
        pts: list[Vec2] = []
        samples = max(8, ceil(1 / sqrt(tolerance)))
        cps = shape.control_points
        for start in range(0, len(cps) - 1, 3):
            p0, p1, p2, p3 = cps[start : start + 4]
            for i in range(samples + 1):
                if pts and i == 0:
                    continue
                t = i / samples
                u = 1 - t
                pts.append(p0 * (u**3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t**3))
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(tuple(pts), closed=shape.closed, inner_loops=loops)
    if isinstance(shape, Path):
        pts: list[Vec2] = []
        for segment in shape.segments:
            flattened = curves_to_polyline(segment, tolerance=tolerance).points()
            if pts:
                pts.extend(flattened[1:])
            else:
                pts.extend(flattened)
        if shape.closed and pts[0] == pts[-1]:
            pts.pop()
        loops = tuple(curves_to_polyline(h, tolerance=tolerance) for h in shape.inner_loops)
        return Polyline(tuple(pts), closed=shape.closed, inner_loops=loops)
    raise TypeError(f"unsupported Shape2D {type(shape).__name__}")


def _area2(points: tuple[Vec2, ...]) -> float:
    return (
        sum(a.x * b.y - b.x * a.y for a, b in zip(points, points[1:] + points[:1], strict=True)) / 2
    )


def _point_in_poly(point: Vec2, poly: tuple[Vec2, ...]) -> bool:
    inside = False
    j = len(poly) - 1
    for i, pi_ in enumerate(poly):
        pj = poly[j]
        if ((pi_.y > point.y) != (pj.y > point.y)) and (
            point.x < (pj.x - pi_.x) * (point.y - pi_.y) / (pj.y - pi_.y) + pi_.x
        ):
            inside = not inside
        j = i
    return inside


def _cross2(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _geometry_tolerance(points: tuple[Vec2, ...], tolerance: float) -> float:
    span = max(
        max(point.x for point in points) - min(point.x for point in points),
        max(point.y for point in points) - min(point.y for point in points),
    )
    return max(span * 1e-12, tolerance * 1e-6, 1e-12)


def _same_point(a: Vec2, b: Vec2, tolerance: float) -> bool:
    return abs(a.x - b.x) <= tolerance and abs(a.y - b.y) <= tolerance


def _point_on_segment(point: Vec2, a: Vec2, b: Vec2, tolerance: float) -> bool:
    if abs(_cross2(a, b, point)) > tolerance:
        return False
    return (
        min(a.x, b.x) - tolerance <= point.x <= max(a.x, b.x) + tolerance
        and min(a.y, b.y) - tolerance <= point.y <= max(a.y, b.y) + tolerance
    )


def _segments_intersect(a: Vec2, b: Vec2, c: Vec2, d: Vec2, tolerance: float) -> bool:
    if (
        max(a.x, b.x) + tolerance < min(c.x, d.x)
        or max(c.x, d.x) + tolerance < min(a.x, b.x)
        or max(a.y, b.y) + tolerance < min(c.y, d.y)
        or max(c.y, d.y) + tolerance < min(a.y, b.y)
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


def _point_in_triangle(point: Vec2, a: Vec2, b: Vec2, c: Vec2, tolerance: float) -> bool:
    return (
        _cross2(a, b, point) >= -tolerance
        and _cross2(b, c, point) >= -tolerance
        and _cross2(c, a, point) >= -tolerance
    )


def _clean_ring(points: tuple[Vec2, ...]) -> tuple[Vec2, ...]:
    clean: list[Vec2] = []
    for point in _dedupe_closed(list(points)):
        if clean and point == clean[-1]:
            continue
        clean.append(point)
    if len(clean) > 1 and clean[0] == clean[-1]:
        clean.pop()
    return tuple(clean)


def _triangulate_simple_polygon(points: tuple[Vec2, ...], *, tolerance: float) -> list[Triangle2]:
    points = _clean_ring(points)
    if len(points) < 3:
        return []
    if _area2(points) < 0:
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
    start: Vec2,
    end: Vec2,
    polygon: tuple[Vec2, ...],
    outer: tuple[Vec2, ...],
    holes: tuple[tuple[Vec2, ...], ...],
    current_hole: int,
    tolerance: float,
) -> bool:
    if _same_point(start, end, tolerance):
        return False

    for fraction in (0.25, 0.5, 0.75):
        sample = Vec2(
            start.x + (end.x - start.x) * fraction,
            start.y + (end.y - start.y) * fraction,
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
    polygon: tuple[Vec2, ...],
    outer: tuple[Vec2, ...],
    holes: tuple[tuple[Vec2, ...], ...],
    hole_index: int,
    *,
    tolerance: float,
) -> tuple[Vec2, ...]:
    hole = holes[hole_index]
    eps = _geometry_tolerance(outer + tuple(point for hole in holes for point in hole), tolerance)
    start_index = max(range(len(hole)), key=lambda index: (hole[index].x, -abs(hole[index].y)))
    start = hole[start_index]
    candidate_indices = list(range(len(polygon)))
    candidate_indices.sort(
        key=lambda index: (
            polygon[index].x < start.x - eps,
            (polygon[index].x - start.x) ** 2 + (polygon[index].y - start.y) ** 2,
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
    outer: tuple[Vec2, ...],
    holes: tuple[tuple[Vec2, ...], ...],
    *,
    tolerance: float,
) -> list[Triangle2]:
    if _area2(outer) < 0:
        outer = tuple(reversed(outer))
    oriented_holes = tuple(tuple(reversed(hole)) if _area2(hole) > 0 else hole for hole in holes)
    polygon = outer
    for hole_index in sorted(
        range(len(oriented_holes)),
        key=lambda index: max(point.x for point in oriented_holes[index]),
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


def _is_self_intersecting(points: tuple[Vec2, ...]) -> bool:
    def ccw(a: Vec2, b: Vec2, c: Vec2) -> bool:
        return (c.y - a.y) * (b.x - a.x) > (b.y - a.y) * (c.x - a.x)

    edges = list(zip(points, points[1:] + points[:1], strict=True))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if abs(i - j) <= 1 or {i, j} == {0, len(edges) - 1}:
                continue
            if ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d):
                return True
    return False


def polygon_to_triangles(shape: Shape2D, *, tolerance: float) -> list[Triangle2]:
    if not shape.closed:
        raise ValueError("polygon_to_triangles requires a closed Shape2D")
    flattened = curves_to_polyline(shape, tolerance=tolerance)
    outer = _dedupe_closed(list(flattened.points()))
    if _is_self_intersecting(outer):
        preview = ", ".join(str(p.tuple()) for p in outer[:3])
        raise WriteError(f"self-intersecting profile near first 3 points: {preview}")
    holes = [
        _dedupe_closed(list(curves_to_polyline(h, tolerance=tolerance).points()))
        for h in flattened.inner_loops
    ]
    if not holes:
        return _triangulate_simple_polygon(outer, tolerance=tolerance)
    return _triangulate_polygon_with_holes(outer, tuple(holes), tolerance=tolerance)


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    n = (b - a).cross(c - a)
    try:
        return n.normalised()
    except ValueError:
        return Vec3(0, 0, 0)


def prism_to_triangles(shape: Prism) -> list[Triangle3]:
    p = shape.corners()
    faces = (
        (0, 2, 1, 0, 3, 2),
        (4, 5, 6, 4, 6, 7),
        (0, 1, 5, 0, 5, 4),
        (1, 2, 6, 1, 6, 5),
        (2, 3, 7, 2, 7, 6),
        (3, 0, 4, 3, 4, 7),
    )
    return [(p[a], p[b], p[c]) for face in faces for a, b, c in (face[:3], face[3:])]


def _basis_for_axis(axis: AxisString | Vec3) -> tuple[Vec3, Vec3, Vec3]:
    w = axis_vector(axis)
    u = Vec3(1, 0, 0) if abs(w.z) == 1 else Vec3(0, 0, 1).cross(w).normalised()
    v = w.cross(u).normalised()
    if axis in {"+y", "-y"}:
        u, v = Vec3(1, 0, 0), Vec3(0, 0, 1)
    elif axis in {"+x", "-x"}:
        u, v = Vec3(0, 1, 0), Vec3(0, 0, 1)
    return u, v, w


def _map2(point: Vec2, origin: Vec3, u: Vec3, v: Vec3) -> Vec3:
    return origin + u * point.x + v * point.y


def extrusion_to_triangles(extrusion: Extrusion, *, tolerance: float) -> list[Triangle3]:
    cap2 = polygon_to_triangles(extrusion.profile, tolerance=tolerance)
    u, v, w = _basis_for_axis(extrusion.axis)
    start = extrusion.offset
    end = extrusion.offset + w * extrusion.distance
    tris: list[Triangle3] = []
    for a, b, c in cap2:
        tris.append((_map2(c, start, u, v), _map2(b, start, u, v), _map2(a, start, u, v)))
        tris.append((_map2(a, end, u, v), _map2(b, end, u, v), _map2(c, end, u, v)))
    loops = [(curves_to_polyline(extrusion.profile, tolerance=tolerance).points(), False)]
    loops.extend(
        (curves_to_polyline(h, tolerance=tolerance).points(), True)
        for h in extrusion.profile.inner_loops
    )
    for loop, is_hole in loops:
        pts = _dedupe_closed(list(loop))
        for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
            a0, b0 = _map2(a, start, u, v), _map2(b, start, u, v)
            a1, b1 = _map2(a, end, u, v), _map2(b, end, u, v)
            if is_hole:
                tris.append((a0, b1, b0))
                tris.append((a0, a1, b1))
            else:
                tris.append((a0, b0, b1))
                tris.append((a0, b1, a1))
    return tris


def revolution_to_triangles(revolution: Revolution, *, tolerance: float) -> list[Triangle3]:
    profile = curves_to_polyline(revolution.profile, tolerance=tolerance)
    pts2 = _dedupe_closed(list(profile.points()))
    axis = revolution.axis_direction.normalised()
    if axis != Vec3(0, 0, 1):
        raise ValueError("Stage 1 revolution tessellation supports +Z axis")
    radius = max(abs(p.x - revolution.axis_origin.x) for p in pts2) or 1.0
    steps = max(12, ceil(abs(revolution.angle_rad) * radius / max(tolerance * 8, 1e-6)))
    steps = min(steps, 160)
    rings: list[list[Vec3]] = []
    for i in range(steps):
        angle = revolution.angle_rad * i / steps
        ca, sa = cos(angle), sin(angle)
        rings.append([Vec3(p.x * ca, p.x * sa, p.y) for p in pts2])
    tris: list[Triangle3] = []
    for i in range(steps):
        nxt = (i + 1) % steps
        for j in range(len(pts2)):
            a = rings[i][j]
            b = rings[i][(j + 1) % len(pts2)]
            c = rings[nxt][(j + 1) % len(pts2)]
            d = rings[nxt][j]
            tris.append((a, b, c))
            tris.append((a, c, d))
    return tris


def sphere_to_triangles(sphere: Sphere, *, tolerance: float) -> list[Triangle3]:
    rings = min(64, max(8, _segments_for_circle(sphere.radius, tolerance) // 2))
    segs = rings * 2
    tris: list[Triangle3] = []
    for i in range(rings):
        theta0 = pi * i / rings
        theta1 = pi * (i + 1) / rings
        for j in range(segs):
            phi0 = 2 * pi * j / segs
            phi1 = 2 * pi * (j + 1) / segs
            pts: list[Vec3] = []
            for theta, phi in ((theta0, phi0), (theta1, phi0), (theta1, phi1), (theta0, phi1)):
                pts.append(
                    sphere.centre
                    + Vec3(
                        sphere.radius * sin(theta) * cos(phi),
                        sphere.radius * sin(theta) * sin(phi),
                        sphere.radius * cos(theta),
                    )
                )
            if pts[0] != pts[1] and pts[1] != pts[2]:
                tris.append((pts[0], pts[1], pts[2]))
            if pts[0] != pts[2] and pts[2] != pts[3]:
                tris.append((pts[0], pts[2], pts[3]))
    return tris


def triangles_for_solid(shape: Shape3D, *, tolerance: float) -> list[Triangle3]:
    if isinstance(shape, Prism):
        return prism_to_triangles(shape)
    if isinstance(shape, Extrusion):
        return extrusion_to_triangles(shape, tolerance=tolerance)
    if isinstance(shape, Revolution):
        return revolution_to_triangles(shape, tolerance=tolerance)
    if isinstance(shape, Sphere):
        return sphere_to_triangles(shape, tolerance=tolerance)
    raise TypeError(f"unsupported Shape3D {type(shape).__name__}")


def normal_for_triangle(triangle: Triangle3) -> Vec3:
    return _normal(*triangle)
