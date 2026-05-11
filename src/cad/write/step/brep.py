from __future__ import annotations

import math

from cad.errors import WriteError
from cad.geom.base import axis_vector
from cad.geom.shapes2d import Circle, Polyline
from cad.geom.shapes3d import Extrusion, Prism
from cad.write.step.ids import IdAllocator


def _f(v: float) -> str:
    return f"{v:.10G}"


def _cp(ids: IdAllocator, x: float, y: float, z: float) -> int:
    return ids.add(f"CARTESIAN_POINT('',({_f(x)},{_f(y)},{_f(z)}))")


def _dir(ids: IdAllocator, x: float, y: float, z: float) -> int:
    return ids.add(f"DIRECTION('',({_f(x)},{_f(y)},{_f(z)}))")


def _vp(ids: IdAllocator, cp_id: int) -> int:
    return ids.add(f"VERTEX_POINT('',#{cp_id})")


def _line(ids: IdAllocator, cp_id: int, dir_id: int) -> int:
    vec_id = ids.add(f"VECTOR('',#{dir_id},1.0)")
    return ids.add(f"LINE('',#{cp_id},#{vec_id})")


def _ec(ids: IdAllocator, vp_s: int, vp_e: int, line_id: int) -> int:
    return ids.add(f"EDGE_CURVE('',#{vp_s},#{vp_e},#{line_id},.T.)")


def _oe(ids: IdAllocator, ec_id: int, forward: bool) -> int:
    sense = ".T." if forward else ".F."
    return ids.add(f"ORIENTED_EDGE('',*,*,#{ec_id},{sense})")


def _el(ids: IdAllocator, oe_ids: list[int]) -> int:
    refs = ",".join(f"#{i}" for i in oe_ids)
    return ids.add(f"EDGE_LOOP('',({refs}))")


def _fob(ids: IdAllocator, el_id: int) -> int:
    return ids.add(f"FACE_OUTER_BOUND('',#{el_id},.T.)")


def _plane(
    ids: IdAllocator,
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
    ref: tuple[float, float, float],
) -> int:
    cp_id = _cp(ids, *origin)
    n_id = _dir(ids, *normal)
    r_id = _dir(ids, *ref)
    a2p_id = ids.add(f"AXIS2_PLACEMENT_3D('',#{cp_id},#{n_id},#{r_id})")
    return ids.add(f"PLANE('',#{a2p_id})")


def _af(ids: IdAllocator, fob_id: int, plane_id: int) -> int:
    return ids.add(f"ADVANCED_FACE('',(#{fob_id}),#{plane_id},.T.)")


def prism_brep(ids: IdAllocator, solid: Prism) -> int:
    """Emit all entities for a box MANIFOLD_SOLID_BREP; return its entity ID."""
    ox, oy, oz = solid.origin.x, solid.origin.y, solid.origin.z
    sx, sy, sz = solid.size.x, solid.size.y, solid.size.z
    x0, x1 = (ox, ox + sx) if sx > 0 else (ox + sx, ox)
    y0, y1 = (oy, oy + sy) if sy > 0 else (oy + sy, oy)
    z0, z1 = (oz, oz + sz) if sz > 0 else (oz + sz, oz)

    coords: list[tuple[float, float, float]] = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    cp_ids = [_cp(ids, *c) for c in coords]
    vp_ids = [_vp(ids, c) for c in cp_ids]

    edge_defs: list[tuple[int, int, tuple[float, float, float]]] = [
        (0, 1, (1, 0, 0)), (1, 2, (0, 1, 0)), (2, 3, (-1, 0, 0)), (3, 0, (0, -1, 0)),
        (4, 5, (1, 0, 0)), (5, 6, (0, 1, 0)), (6, 7, (-1, 0, 0)), (7, 4, (0, -1, 0)),
        (0, 4, (0, 0, 1)), (1, 5, (0, 0, 1)), (2, 6, (0, 0, 1)),  (3, 7, (0, 0, 1)),
    ]
    ec_ids: list[int] = []
    for vi, vj, dxyz in edge_defs:
        line_id = _line(ids, cp_ids[vi], _dir(ids, *dxyz))
        ec_ids.append(_ec(ids, vp_ids[vi], vp_ids[vj], line_id))

    edge_lu: dict[tuple[int, int], tuple[int, bool]] = {}
    for idx, (vi, vj, _) in enumerate(edge_defs):
        edge_lu[(vi, vj)] = (idx, True)
        edge_lu[(vj, vi)] = (idx, False)

    face_defs: list[tuple[
        list[int],
        tuple[float, float, float],
        tuple[float, float, float],
        int,
    ]] = [
        ([0, 3, 2, 1], (0,  0, -1), ( 1, 0, 0), 0),
        ([4, 5, 6, 7], (0,  0,  1), ( 1, 0, 0), 4),
        ([0, 1, 5, 4], (0, -1,  0), ( 1, 0, 0), 0),
        ([3, 7, 6, 2], (0,  1,  0), (-1, 0, 0), 3),
        ([1, 2, 6, 5], (1,  0,  0), ( 0, 1, 0), 1),
        ([0, 4, 7, 3], (-1, 0,  0), ( 0, 1, 0), 0),
    ]

    af_ids: list[int] = []
    for vloop, normal, ref, ov in face_defs:
        n = len(vloop)
        oe_ids: list[int] = []
        for k in range(n):
            ec_idx, forward = edge_lu[(vloop[k], vloop[(k + 1) % n])]
            oe_ids.append(_oe(ids, ec_ids[ec_idx], forward))
        el_id = _el(ids, oe_ids)
        fob_id = _fob(ids, el_id)
        plane_id = _plane(ids, coords[ov], normal, ref)
        af_ids.append(_af(ids, fob_id, plane_id))

    shell_refs = ",".join(f"#{i}" for i in af_ids)
    cs_id = ids.add(f"CLOSED_SHELL('',({shell_refs}))")
    return ids.add(f"MANIFOLD_SOLID_BREP('',#{cs_id})")


def _profile_points(profile: Polyline | Circle, segments: int = 32) -> list[tuple[float, float]]:
    """Return a deduplicated list of XY points for *profile*.

    Circles are discretised into *segments* vertices.
    For Polyline the closing vertex is dropped.
    """
    if isinstance(profile, Circle):
        cx, cy = profile.centre.x, profile.centre.y
        r = profile.radius
        return [
            (cx + r * math.cos(2 * math.pi * i / segments),
             cy + r * math.sin(2 * math.pi * i / segments))
            for i in range(segments)
        ]
    pts = list(profile.points())
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    return [(p.x, p.y) for p in pts]


def extrusion_brep(ids: IdAllocator, solid: Extrusion) -> int:
    """Emit all entities for a polygonal extrusion MANIFOLD_SOLID_BREP; return its entity ID.

    Only +z and -z axis strings and unit Vec3 directions within 1e-9 of those are supported.
    The profile must be a closed Polyline or Circle.
    """
    if not isinstance(solid.profile, (Polyline, Circle)):
        raise WriteError(
            f"STEP Extrusion only supports Polyline or Circle profiles; "
            f"got {type(solid.profile).__name__}"
        )

    axis_vec = axis_vector(solid.axis)
    ax, ay, az = axis_vec.x, axis_vec.y, axis_vec.z
    if abs(ax) > 1e-9 or abs(ay) > 1e-9:
        raise WriteError("STEP Extrusion only supports +z / -z axis directions")

    ox, oy, oz = solid.offset.x, solid.offset.y, solid.offset.z
    d = solid.distance
    sign = 1.0 if az > 0 else -1.0
    z_bot = oz
    z_top = oz + sign * d

    xy_pts = _profile_points(solid.profile)
    n = len(xy_pts)
    if n < 3:
        raise WriteError("Extrusion profile must have at least 3 vertices")

    bot = [(x + ox, y + oy, z_bot) for x, y in xy_pts]
    top = [(x + ox, y + oy, z_top) for x, y in xy_pts]

    # Cartesian points + vertex points
    cp_bot = [_cp(ids, *p) for p in bot]
    cp_top = [_cp(ids, *p) for p in top]
    vp_bot = [_vp(ids, cp) for cp in cp_bot]
    vp_top = [_vp(ids, cp) for cp in cp_top]

    # Bottom edges: bot[i] → bot[(i+1)%n]
    ec_bot: list[int] = []
    for i in range(n):
        j = (i + 1) % n
        dx = bot[j][0] - bot[i][0]
        dy = bot[j][1] - bot[i][1]
        length = math.hypot(dx, dy)
        dir_id = _dir(ids, dx / length, dy / length, 0.0)
        ec_bot.append(_ec(ids, vp_bot[i], vp_bot[j], _line(ids, cp_bot[i], dir_id)))

    # Top edges: top[i] → top[(i+1)%n]
    ec_top: list[int] = []
    for i in range(n):
        j = (i + 1) % n
        dx = top[j][0] - top[i][0]
        dy = top[j][1] - top[i][1]
        length = math.hypot(dx, dy)
        dir_id = _dir(ids, dx / length, dy / length, 0.0)
        ec_top.append(_ec(ids, vp_top[i], vp_top[j], _line(ids, cp_top[i], dir_id)))

    # Vertical edges: bot[i] → top[i]
    ec_vert: list[int] = []
    for i in range(n):
        dz = z_top - z_bot
        dir_id = _dir(ids, 0.0, 0.0, 1.0 if dz > 0 else -1.0)
        ec_vert.append(_ec(ids, vp_bot[i], vp_top[i], _line(ids, cp_bot[i], dir_id)))

    af_ids: list[int] = []

    # Bottom face: normal (0,0,-1) if +z extrusion, normal (0,0,+1) if -z
    # For outward normal, bottom face normal points away from the solid
    bot_normal = (0.0, 0.0, -sign)
    ref_dir = (1.0, 0.0, 0.0) if abs(xy_pts[0][0] - xy_pts[1][0]) > 1e-9 else (0.0, 1.0, 0.0)
    # Bottom loop: reverse order for outward normal
    oe_bot = [_oe(ids, ec_bot[(n - 1 - i) % n], False) for i in range(n)]
    el_bot = _el(ids, oe_bot)
    fob_bot = _fob(ids, el_bot)
    plane_bot = _plane(ids, bot[0], bot_normal, ref_dir)
    af_ids.append(_af(ids, fob_bot, plane_bot))

    # Top face: normal (0,0,+sign)
    top_normal = (0.0, 0.0, sign)
    oe_top = [_oe(ids, ec_top[i], True) for i in range(n)]
    el_top = _el(ids, oe_top)
    fob_top = _fob(ids, el_top)
    plane_top = _plane(ids, top[0], top_normal, ref_dir)
    af_ids.append(_af(ids, fob_top, plane_top))

    # Side faces: quad for each edge
    for i in range(n):
        j = (i + 1) % n
        dx = xy_pts[j][0] - xy_pts[i][0]
        dy = xy_pts[j][1] - xy_pts[i][1]
        length = math.hypot(dx, dy)
        outward_normal = (dy / length, -dx / length, 0.0)

        oe_ids = [
            _oe(ids, ec_bot[i], True),
            _oe(ids, ec_vert[j], True),
            _oe(ids, ec_top[i], False),
            _oe(ids, ec_vert[i], False),
        ]
        el_id = _el(ids, oe_ids)
        fob_id = _fob(ids, el_id)
        plane_id = _plane(ids, bot[i], outward_normal, (0.0, 0.0, 1.0))
        af_ids.append(_af(ids, fob_id, plane_id))

    shell_refs = ",".join(f"#{i}" for i in af_ids)
    cs_id = ids.add(f"CLOSED_SHELL('',({shell_refs}))")
    return ids.add(f"MANIFOLD_SOLID_BREP('',#{cs_id})")
