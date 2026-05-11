from __future__ import annotations

from cad.geom.shapes3d import Prism
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
        oe_ids = [
            _oe(ids, ec_ids[edge_lu[(vloop[k], vloop[(k + 1) % n])][0]],
                edge_lu[(vloop[k], vloop[(k + 1) % n])][1])
            for k in range(n)
        ]
        el_id = _el(ids, oe_ids)
        fob_id = _fob(ids, el_id)
        plane_id = _plane(ids, coords[ov], normal, ref)
        af_ids.append(_af(ids, fob_id, plane_id))

    shell_refs = ",".join(f"#{i}" for i in af_ids)
    cs_id = ids.add(f"CLOSED_SHELL('',({shell_refs}))")
    return ids.add(f"MANIFOLD_SOLID_BREP('',#{cs_id})")
