import numpy as np

_EPS = 1e-12


# ------------------------------------------------------------
# Basic geometry / topology helpers
# ------------------------------------------------------------


def _edge_key(a, b):
    a = int(a)
    b = int(b)
    return (a, b) if a < b else (b, a)


def _cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def face_normals(V, F, unit=False):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    if len(F) == 0:
        return np.empty((0, 3), dtype=np.float64)

    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])

    if not unit:
        return n

    l = np.linalg.norm(n, axis=1)
    out = np.zeros_like(n)
    good = l > _EPS
    out[good] = n[good] / l[good, None]
    return out


def vertex_normals(V, F):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    n = np.zeros_like(V)
    fn = face_normals(V, F, unit=False)

    if len(F) == 0:
        return n

    np.add.at(n, F[:, 0], fn)
    np.add.at(n, F[:, 1], fn)
    np.add.at(n, F[:, 2], fn)

    l = np.linalg.norm(n, axis=1)
    good = l > _EPS
    n[good] /= l[good, None]

    return n


def unique_edges(F):
    F = np.asarray(F, dtype=np.int64)

    if len(F) == 0:
        return np.empty((0, 2), dtype=np.int64)

    E = np.vstack((F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]))
    E = np.sort(E, axis=1)
    return np.unique(E, axis=0)


def edge_lengths(V, E):
    V = np.asarray(V, dtype=np.float64)
    E = np.asarray(E, dtype=np.int64)

    if len(E) == 0:
        return np.empty(0, dtype=np.float64)

    return np.linalg.norm(V[E[:, 1]] - V[E[:, 0]], axis=1)


def build_edge_faces(F):
    edge_faces = {}

    for fi, tri in enumerate(np.asarray(F, dtype=np.int64)):
        a, b, c = map(int, tri)

        for u, v in ((a, b), (b, c), (c, a)):
            key = _edge_key(u, v)
            if key not in edge_faces:
                edge_faces[key] = [fi]
            else:
                edge_faces[key].append(fi)

    return edge_faces


def build_vertex_faces(F, n_vertices):
    vf = [[] for _ in range(n_vertices)]

    for fi, tri in enumerate(np.asarray(F, dtype=np.int64)):
        for v in tri:
            vf[int(v)].append(fi)

    return vf


def build_vertex_neighbors(F, n_vertices):
    nb = [set() for _ in range(n_vertices)]

    for tri in np.asarray(F, dtype=np.int64):
        a, b, c = map(int, tri)

        nb[a].add(b)
        nb[a].add(c)

        nb[b].add(a)
        nb[b].add(c)

        nb[c].add(a)
        nb[c].add(b)

    return nb


def remove_degenerate_faces(V, F, area_eps=1e-14):
    F = np.asarray(F, dtype=np.int64)

    if len(F) == 0:
        return F.reshape((0, 3))

    mask = (F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 2] != F[:, 0])
    F = F[mask]

    if len(F) == 0:
        return F.reshape((0, 3))

    n = face_normals(V, F, unit=False)
    mask = np.linalg.norm(n, axis=1) > area_eps
    F = F[mask]

    if len(F) == 0:
        return F.reshape((0, 3))

    # Remove duplicate triangles, ignoring orientation.
    SF = np.sort(F, axis=1)
    _, keep = np.unique(SF, axis=0, return_index=True)
    keep = np.sort(keep)

    return F[keep].astype(np.int64, copy=False)


def compact_mesh(V, F):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    if len(F) == 0:
        return V[:0].copy(), F.reshape((0, 3))

    used = np.unique(F.ravel())

    remap = -np.ones(len(V), dtype=np.int64)
    remap[used] = np.arange(len(used), dtype=np.int64)

    return V[used].copy(), remap[F]


def triangle_quality(V, F):
    """
    Equilateral triangle -> 1.
    Degenerate triangle -> 0.
    """
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    if len(F) == 0:
        return np.empty(0, dtype=np.float64)

    A = V[F[:, 0]]
    B = V[F[:, 1]]
    C = V[F[:, 2]]

    ab = np.linalg.norm(B - A, axis=1)
    bc = np.linalg.norm(C - B, axis=1)
    ca = np.linalg.norm(A - C, axis=1)

    area2 = np.linalg.norm(np.cross(B - A, C - A), axis=1)
    denom = ab * ab + bc * bc + ca * ca

    q = np.zeros(len(F), dtype=np.float64)
    good = denom > _EPS

    # q = 4 sqrt(3) A / sum(edge_length^2)
    # area2 = 2A
    q[good] = 2.0 * np.sqrt(3.0) * area2[good] / denom[good]

    return np.clip(q, 0.0, 1.0)


def mesh_stats(V, F):
    E = unique_edges(F)
    L = edge_lengths(V, E)
    Q = triangle_quality(V, F)

    if len(L) == 0:
        return {}

    return {
        "vertices": int(len(V)),
        "faces": int(len(F)),
        "edges": int(len(E)),
        "edge_min": float(np.min(L)),
        "edge_mean": float(np.mean(L)),
        "edge_max": float(np.max(L)),
        "quality_min": float(np.min(Q)) if len(Q) else 0.0,
        "quality_mean": float(np.mean(Q)) if len(Q) else 0.0,
    }


# ------------------------------------------------------------
# Polygon triangulation
# ------------------------------------------------------------


def _clean_polygon_indices(face):
    ids = []

    for x in face:
        ix = int(x)

        # Allows padded polygon arrays using -1.
        if ix < 0:
            continue

        if len(ids) == 0 or ids[-1] != ix:
            ids.append(ix)

    if len(ids) > 1 and ids[0] == ids[-1]:
        ids.pop()

    return ids


def _polygon_normal(V, ids):
    pts = V[np.asarray(ids, dtype=np.int64)]
    n = np.zeros(3, dtype=np.float64)

    for i in range(len(pts)):
        n += np.cross(pts[i], pts[(i + 1) % len(pts)])

    return n


def _signed_area_2d(xy):
    if len(xy) < 3:
        return 0.0

    x = xy[:, 0]
    y = xy[:, 1]

    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _point_in_tri_2d_oriented(p, a, b, c, orient, eps=1e-12):
    return (
        orient * _cross2(b - a, p - a) >= -eps
        and orient * _cross2(c - b, p - b) >= -eps
        and orient * _cross2(a - c, p - c) >= -eps
    )


def _triangulate_polygon(V, face):
    ids = _clean_polygon_indices(face)

    if len(ids) < 3:
        return []

    if len(ids) == 3:
        return [ids]

    n = _polygon_normal(V, ids)

    if np.linalg.norm(n) < _EPS:
        # Degenerate fallback.
        return [[ids[0], ids[i], ids[i + 1]] for i in range(1, len(ids) - 1)]

    # Project polygon to its dominant 2D plane.
    drop_axis = int(np.argmax(np.abs(n)))
    keep_axes = [0, 1, 2]
    keep_axes.pop(drop_axis)

    xy = V[np.asarray(ids, dtype=np.int64)][:, keep_axes].astype(np.float64)

    area = _signed_area_2d(xy)

    if abs(area) < _EPS:
        return [[ids[0], ids[i], ids[i + 1]] for i in range(1, len(ids) - 1)]

    orient = 1.0 if area > 0.0 else -1.0

    work_ids = list(ids)
    work_xy = xy.copy()
    tris = []

    guard = 0
    max_guard = len(work_ids) * len(work_ids) + 10

    while len(work_ids) > 3 and guard < max_guard:
        guard += 1
        m = len(work_ids)
        ear_found = False

        for i in range(m):
            ip = (i - 1) % m
            inext = (i + 1) % m

            a = work_xy[ip]
            b = work_xy[i]
            c = work_xy[inext]

            # Ear must be convex.
            if orient * _cross2(b - a, c - a) <= 1e-14:
                continue

            contains_other_vertex = False

            for j in range(m):
                if j == ip or j == i or j == inext:
                    continue

                if _point_in_tri_2d_oriented(work_xy[j], a, b, c, orient, eps=1e-14):
                    contains_other_vertex = True
                    break

            if contains_other_vertex:
                continue

            tris.append([work_ids[ip], work_ids[i], work_ids[inext]])

            del work_ids[i]
            work_xy = np.delete(work_xy, i, axis=0)

            ear_found = True
            break

        if not ear_found:
            # Non-simple or numerically awkward polygon fallback.
            tris.extend(
                [[work_ids[0], work_ids[i], work_ids[i + 1]] for i in range(1, len(work_ids) - 1)]
            )
            return tris

    if len(work_ids) == 3:
        tris.append([work_ids[0], work_ids[1], work_ids[2]])

    return tris


def triangulate_faces(V, faces):
    """
    Converts triangle / quad / n-gon faces to triangles.

    faces may be:
      - np.ndarray of shape (m, 3)
      - np.ndarray of shape (m, k), with optional -1 padding
      - list of lists, e.g. [[0,1,2,3], [4,5,6]]
    """
    V = np.asarray(V, dtype=np.float64)

    if isinstance(faces, np.ndarray) and faces.ndim == 2 and faces.shape[1] == 3:
        return faces.astype(np.int64, copy=True)

    if isinstance(faces, np.ndarray) and faces.ndim == 2:
        iterable = [row for row in faces]
    else:
        iterable = faces

    tris = []

    for face in iterable:
        tris.extend(_triangulate_polygon(V, face))

    if len(tris) == 0:
        return np.empty((0, 3), dtype=np.int64)

    return np.asarray(tris, dtype=np.int64)


# ------------------------------------------------------------
# Feature / boundary protection
# ------------------------------------------------------------


def detect_protected_edges_and_vertices(
    V,
    F,
    feature_angle_degrees=50.0,
    protect_boundary=True,
    protect_nonmanifold=True,
):
    """
    Boundary edges and sharp feature edges are protected.

    feature_angle_degrees:
        If angle between adjacent face normals exceeds this, edge is protected.
        Use None to protect only boundaries/nonmanifold edges.
    """
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    edge_faces = build_edge_faces(F)
    fn = face_normals(V, F, unit=True)

    protected_edges = set()

    if feature_angle_degrees is not None:
        cos_limit = np.cos(np.deg2rad(float(feature_angle_degrees)))
    else:
        cos_limit = None

    for edge, flist in edge_faces.items():
        if len(flist) == 1:
            if protect_boundary:
                protected_edges.add(edge)

        elif len(flist) == 2:
            if cos_limit is not None:
                d = float(np.dot(fn[flist[0]], fn[flist[1]]))
                if d < cos_limit:
                    protected_edges.add(edge)

        else:
            if protect_nonmanifold:
                protected_edges.add(edge)

    protected_vertices = np.zeros(len(V), dtype=bool)

    for a, b in protected_edges:
        protected_vertices[a] = True
        protected_vertices[b] = True

    return protected_edges, protected_vertices, edge_faces


# ------------------------------------------------------------
# Operation 1: split long edges
# ------------------------------------------------------------


def split_long_edges(V, F, target_edge_length, long_factor=4.0 / 3.0):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    h = float(target_edge_length)

    E = unique_edges(F)
    L = edge_lengths(V, E)

    long_edges = E[long_factor * h < L]

    if len(long_edges) == 0:
        return V.copy(), F.copy(), 0

    split_map = {}
    new_vertices = []

    for e in long_edges:
        a, b = int(e[0]), int(e[1])
        key = _edge_key(a, b)

        split_map[key] = len(V) + len(new_vertices)
        new_vertices.append(0.5 * (V[a] + V[b]))

    V2 = np.vstack((V, np.asarray(new_vertices, dtype=np.float64)))

    new_faces = []

    for tri in F:
        a, b, c = map(int, tri)

        m_ab = split_map.get(_edge_key(a, b))
        m_bc = split_map.get(_edge_key(b, c))
        m_ca = split_map.get(_edge_key(c, a))

        nsplit = int(m_ab is not None) + int(m_bc is not None) + int(m_ca is not None)

        if nsplit == 0:
            new_faces.append([a, b, c])

        elif nsplit == 1:
            if m_ab is not None:
                new_faces.append([a, m_ab, c])
                new_faces.append([m_ab, b, c])

            elif m_bc is not None:
                new_faces.append([b, m_bc, a])
                new_faces.append([m_bc, c, a])

            else:
                new_faces.append([c, m_ca, b])
                new_faces.append([m_ca, a, b])

        elif nsplit == 2:
            if m_ab is not None and m_bc is not None:
                new_faces.append([m_ab, b, m_bc])
                new_faces.append([a, m_ab, c])
                new_faces.append([m_ab, m_bc, c])

            elif m_bc is not None and m_ca is not None:
                new_faces.append([m_bc, c, m_ca])
                new_faces.append([b, m_bc, a])
                new_faces.append([m_bc, m_ca, a])

            else:
                new_faces.append([m_ca, a, m_ab])
                new_faces.append([c, m_ca, b])
                new_faces.append([m_ca, m_ab, b])

        else:
            new_faces.append([a, m_ab, m_ca])
            new_faces.append([m_ab, b, m_bc])
            new_faces.append([m_ca, m_bc, c])
            new_faces.append([m_ab, m_bc, m_ca])

    F2 = np.asarray(new_faces, dtype=np.int64)
    F2 = remove_degenerate_faces(V2, F2)

    return V2, F2, len(long_edges)


# ------------------------------------------------------------
# Operation 2: collapse short edges
# ------------------------------------------------------------


def _collapse_topology_ok(F, edge_faces, neighbors, u, v):
    key = _edge_key(u, v)
    flist = edge_faces.get(key, [])

    # Conservative: collapse only clean interior manifold edges.
    if len(flist) != 2:
        return False

    common = neighbors[u].intersection(neighbors[v])

    opposite = set()

    for fi in flist:
        for x in F[fi]:
            x = int(x)
            if x != u and x != v:
                opposite.add(x)

    # Link condition for triangular manifold edge collapse.
    return common == opposite


def _collapse_geometry_ok(
    V,
    F,
    vertex_faces,
    unit_face_normals,
    u,
    v,
    new_point,
    area_eps=1e-14,
    min_normal_dot=0.0,
):
    affected = set(vertex_faces[u] + vertex_faces[v])

    for fi in affected:
        tri = F[fi]

        has_u = np.any(tri == u)
        has_v = np.any(tri == v)

        if has_u and has_v:
            # Incident face vanishes after collapse.
            continue

        pts = []
        ids = []

        for idx in tri:
            idx = int(idx)

            if idx == u or idx == v:
                pts.append(new_point)
                ids.append(u)
            else:
                pts.append(V[idx])
                ids.append(idx)

        if len(set(ids)) < 3:
            return False

        p0, p1, p2 = pts
        n = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(n)

        if ln <= area_eps:
            return False

        oldn = unit_face_normals[fi]

        if np.linalg.norm(oldn) > _EPS:
            if float(np.dot(n / ln, oldn)) < min_normal_dot:
                return False

    return True


def collapse_short_edges(
    V,
    F,
    target_edge_length,
    protected_vertices,
    short_factor=4.0 / 5.0,
    min_normal_dot=0.0,
):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    h = float(target_edge_length)

    E = unique_edges(F)
    L = edge_lengths(V, E)
    order = np.argsort(L)

    edge_faces = build_edge_faces(F)
    vertex_faces = build_vertex_faces(F, len(V))
    neighbors = build_vertex_neighbors(F, len(V))
    fn = face_normals(V, F, unit=True)

    touched = np.zeros(len(V), dtype=bool)
    selected = []

    for idx in order:
        if L[idx] >= short_factor * h:
            break

        u, v = map(int, E[idx])

        if protected_vertices[u] or protected_vertices[v]:
            continue

        if touched[u] or touched[v]:
            continue

        if not _collapse_topology_ok(F, edge_faces, neighbors, u, v):
            continue

        new_point = 0.5 * (V[u] + V[v])

        if not _collapse_geometry_ok(
            V,
            F,
            vertex_faces,
            fn,
            u,
            v,
            new_point,
            min_normal_dot=min_normal_dot,
        ):
            continue

        selected.append((u, v, new_point))
        touched[u] = True
        touched[v] = True

    if len(selected) == 0:
        return V.copy(), F.copy(), 0

    V2 = V.copy()
    replace = np.arange(len(V), dtype=np.int64)

    for u, v, p in selected:
        keep = int(u)
        remove = int(v)

        V2[keep] = p
        replace[remove] = keep

    F2 = replace[F]
    F2 = remove_degenerate_faces(V2, F2)
    V2, F2 = compact_mesh(V2, F2)

    return V2, F2, len(selected)


# ------------------------------------------------------------
# Operation 3: flip edges to improve valence
# ------------------------------------------------------------


def _orient_face_to_normal(V, face, target_normal):
    f = np.asarray(face, dtype=np.int64)
    n = np.cross(V[f[1]] - V[f[0]], V[f[2]] - V[f[0]])

    if float(np.dot(n, target_normal)) < 0.0:
        return np.array([f[0], f[2], f[1]], dtype=np.int64)

    return f


def flip_edges(
    V,
    F,
    protected_edges,
    protected_vertices,
    min_quality_ratio=0.8,
    min_normal_dot=0.0,
):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    edge_faces = build_edge_faces(F)
    neighbors = build_vertex_neighbors(F, len(V))
    valence = np.asarray([len(x) for x in neighbors], dtype=np.int64)
    fn = face_normals(V, F, unit=True)

    F2 = F.copy()
    touched_vertices = set()
    n_flipped = 0

    for edge, flist in edge_faces.items():
        if len(flist) != 2:
            continue

        if edge in protected_edges:
            continue

        f1, f2 = flist
        tri1 = F[f1]
        tri2 = F[f2]

        a, b = edge

        c_candidates = [int(x) for x in tri1 if int(x) != a and int(x) != b]
        d_candidates = [int(x) for x in tri2 if int(x) != a and int(x) != b]

        if len(c_candidates) != 1 or len(d_candidates) != 1:
            continue

        c = c_candidates[0]
        d = d_candidates[0]

        if c == d:
            continue

        if (
            protected_vertices[a]
            or protected_vertices[b]
            or protected_vertices[c]
            or protected_vertices[d]
        ):
            continue

        if (
            a in touched_vertices
            or b in touched_vertices
            or c in touched_vertices
            or d in touched_vertices
        ):
            continue

        new_edge = _edge_key(c, d)

        if new_edge in edge_faces:
            continue

        before = (
            (valence[a] - 6) ** 2
            + (valence[b] - 6) ** 2
            + (valence[c] - 6) ** 2
            + (valence[d] - 6) ** 2
        )

        after = (
            (valence[a] - 1 - 6) ** 2
            + (valence[b] - 1 - 6) ** 2
            + (valence[c] + 1 - 6) ** 2
            + (valence[d] + 1 - 6) ** 2
        )

        if after >= before:
            continue

        old_q = triangle_quality(V, np.vstack((tri1, tri2)))
        old_min_q = float(np.min(old_q)) if len(old_q) else 0.0

        avg_n = fn[f1] + fn[f2]

        if np.linalg.norm(avg_n) < _EPS:
            continue

        nf1 = _orient_face_to_normal(V, [c, d, a], avg_n)
        nf2 = _orient_face_to_normal(V, [d, c, b], avg_n)

        new_q = triangle_quality(V, np.vstack((nf1, nf2)))
        new_min_q = float(np.min(new_q)) if len(new_q) else 0.0

        if new_min_q + 1e-14 < min_quality_ratio * old_min_q:
            continue

        avg_n_unit = avg_n / np.linalg.norm(avg_n)

        good_geometry = True

        for nf in (nf1, nf2):
            n = np.cross(V[nf[1]] - V[nf[0]], V[nf[2]] - V[nf[0]])
            ln = np.linalg.norm(n)

            if ln <= _EPS:
                good_geometry = False
                break

            if float(np.dot(n / ln, avg_n_unit)) < min_normal_dot:
                good_geometry = False
                break

        if not good_geometry:
            continue

        F2[f1] = nf1
        F2[f2] = nf2

        touched_vertices.update([a, b, c, d])
        n_flipped += 1

    if n_flipped == 0:
        return V.copy(), F.copy(), 0

    F2 = remove_degenerate_faces(V, F2)

    return V.copy(), F2, n_flipped


# ------------------------------------------------------------
# Operation 4: tangential smoothing + projection
# ------------------------------------------------------------


def _closest_points_on_segments(p, A, B):
    AB = B - A
    denom = np.sum(AB * AB, axis=1)
    denom_safe = np.where(denom > _EPS, denom, 1.0)

    t = np.sum((p[None, :] - A) * AB, axis=1) / denom_safe
    t = np.clip(t, 0.0, 1.0)

    return A + t[:, None] * AB


def closest_point_on_triangle_mesh(p, V, F):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    A = V[F[:, 0]]
    B = V[F[:, 1]]
    C = V[F[:, 2]]

    AB = B - A
    AC = C - A

    N = np.cross(AB, AC)
    N2 = np.sum(N * N, axis=1)
    N2safe = np.where(N2 > _EPS, N2, 1.0)

    AP = p[None, :] - A

    tplane = np.sum(AP * N, axis=1) / N2safe
    Q = p[None, :] - tplane[:, None] * N

    # Barycentric coordinates of projected point.
    v0 = AB
    v1 = AC
    v2 = Q - A

    d00 = np.sum(v0 * v0, axis=1)
    d01 = np.sum(v0 * v1, axis=1)
    d11 = np.sum(v1 * v1, axis=1)
    d20 = np.sum(v2 * v0, axis=1)
    d21 = np.sum(v2 * v1, axis=1)

    denom = d00 * d11 - d01 * d01
    denom_safe = np.where(np.abs(denom) > _EPS, denom, 1.0)

    vb = (d11 * d20 - d01 * d21) / denom_safe
    wb = (d00 * d21 - d01 * d20) / denom_safe
    ub = 1.0 - vb - wb

    inside = (N2 > _EPS) & (np.abs(denom) > _EPS) & (ub >= -1e-12) & (vb >= -1e-12) & (wb >= -1e-12)

    CPab = _closest_points_on_segments(p, A, B)
    CPbc = _closest_points_on_segments(p, B, C)
    CPca = _closest_points_on_segments(p, C, A)

    d2ab = np.sum((CPab - p[None, :]) ** 2, axis=1)
    d2bc = np.sum((CPbc - p[None, :]) ** 2, axis=1)
    d2ca = np.sum((CPca - p[None, :]) ** 2, axis=1)

    CP = CPab.copy()
    d2 = d2ab.copy()

    mask = d2bc < d2
    CP[mask] = CPbc[mask]
    d2[mask] = d2bc[mask]

    mask = d2ca < d2
    CP[mask] = CPca[mask]
    d2[mask] = d2ca[mask]

    d2plane = np.sum((Q - p[None, :]) ** 2, axis=1)

    mask = inside & (d2plane <= d2)
    CP[mask] = Q[mask]
    d2[mask] = d2plane[mask]

    best = int(np.argmin(d2))

    return CP[best]


def project_points_to_mesh(P, V, F):
    P = np.asarray(P, dtype=np.float64)
    out = np.empty_like(P)

    for i in range(len(P)):
        out[i] = closest_point_on_triangle_mesh(P[i], V, F)

    return out


def smooth_vertices(
    V,
    F,
    protected_vertices,
    relaxation=0.5,
    project_to_vertices=None,
    project_to_faces=None,
):
    V = np.asarray(V, dtype=np.float64)
    F = np.asarray(F, dtype=np.int64)

    nb = build_vertex_neighbors(F, len(V))
    vn = vertex_normals(V, F)

    V2 = V.copy()
    movable = []

    for i in range(len(V)):
        if protected_vertices[i]:
            continue

        if len(nb[i]) == 0:
            continue

        nbrs = np.fromiter(nb[i], dtype=np.int64)
        centroid = np.mean(V[nbrs], axis=0)

        d = centroid - V[i]
        n = vn[i]

        # Tangential component only.
        if np.linalg.norm(n) > _EPS:
            d = d - np.dot(d, n) * n

        V2[i] = V[i] + float(relaxation) * d
        movable.append(i)

    if project_to_vertices is not None and project_to_faces is not None and len(movable) > 0:
        idx = np.asarray(movable, dtype=np.int64)
        V2[idx] = project_points_to_mesh(
            V2[idx],
            project_to_vertices,
            project_to_faces,
        )

    return V2


# ------------------------------------------------------------
# Main isotropic remesher
# ------------------------------------------------------------


def isotropic_remesh(
    vertices,
    faces,
    target_edge_length: float | None = None,
    iterations: int = 10,
    feature_angle_degrees: float | None = 50.0,
    protect_boundary: bool = True,
    long_factor: float = 4.0 / 3.0,
    short_factor: float = 4.0 / 5.0,
    relaxation: float = 0.5,
    project: bool = True,
    verbose: bool = False,
):
    """
    Pure NumPy feature-preserving isotropic surface remeshing.

    Parameters
    ----------
    vertices : (n, 3) float array
        Input vertex positions.

    faces : array or list of lists
        Input faces. May contain triangles, quads, or n-gons.

    target_edge_length : float or None
        Desired edge length. If None, uses mean input edge length.

    iterations : int
        Number of remeshing iterations.

    feature_angle_degrees : float or None
        Sharp-feature protection threshold.
        Edges with dihedral angle above this are frozen/protected.
        Use None to protect only boundaries/nonmanifold edges.

    protect_boundary : bool
        Whether boundary vertices/edges should be preserved.

    project : bool
        If True, smooth vertices are projected back to the original surface.

    Returns
    -------
    V, F
        Remeshed vertices and triangular faces.
    """
    V = np.asarray(vertices, dtype=np.float64).copy()

    # Step 1: convert arbitrary polygon faces to triangles.
    F = triangulate_faces(V, faces)

    F = remove_degenerate_faces(V, F)
    V, F = compact_mesh(V, F)

    original_vertices = V.copy()
    original_faces = F.copy()

    if target_edge_length is None:
        E = unique_edges(F)
        L = edge_lengths(V, E)

        if len(L) == 0:
            return V, F

        target_edge_length = float(np.mean(L))
    else:
        target_edge_length = float(target_edge_length)

    for it in range(int(iterations)):
        # 1. Split long edges.
        protected_edges, protected_vertices, _ = detect_protected_edges_and_vertices(
            V,
            F,
            feature_angle_degrees=feature_angle_degrees,
            protect_boundary=protect_boundary,
        )

        V, F, nsplit = split_long_edges(
            V,
            F,
            target_edge_length,
            long_factor=long_factor,
        )

        F = remove_degenerate_faces(V, F)
        V, F = compact_mesh(V, F)

        # 2. Collapse short edges.
        protected_edges, protected_vertices, _ = detect_protected_edges_and_vertices(
            V,
            F,
            feature_angle_degrees=feature_angle_degrees,
            protect_boundary=protect_boundary,
        )

        V, F, ncollapse = collapse_short_edges(
            V,
            F,
            target_edge_length,
            protected_vertices=protected_vertices,
            short_factor=short_factor,
        )

        # 3. Flip edges to improve valence / triangle regularity.
        protected_edges, protected_vertices, _ = detect_protected_edges_and_vertices(
            V,
            F,
            feature_angle_degrees=feature_angle_degrees,
            protect_boundary=protect_boundary,
        )

        V, F, nflips = flip_edges(
            V,
            F,
            protected_edges=protected_edges,
            protected_vertices=protected_vertices,
        )

        # 4. Tangential relaxation and projection.
        protected_edges, protected_vertices, _ = detect_protected_edges_and_vertices(
            V,
            F,
            feature_angle_degrees=feature_angle_degrees,
            protect_boundary=protect_boundary,
        )

        if project:
            V = smooth_vertices(
                V,
                F,
                protected_vertices,
                relaxation=relaxation,
                project_to_vertices=original_vertices,
                project_to_faces=original_faces,
            )
        else:
            V = smooth_vertices(
                V,
                F,
                protected_vertices,
                relaxation=relaxation,
            )

        F = remove_degenerate_faces(V, F)
        V, F = compact_mesh(V, F)

        if verbose:
            s = mesh_stats(V, F)

            print(
                f"iter {it + 1:02d}: "
                f"split={nsplit}, collapse={ncollapse}, flip={nflips}, "
                f"V={s.get('vertices', 0)}, F={s.get('faces', 0)}, "
                f"edge_mean={s.get('edge_mean', 0):.6g}, "
                f"edge_min={s.get('edge_min', 0):.6g}, "
                f"edge_max={s.get('edge_max', 0):.6g}, "
                f"q_mean={s.get('quality_mean', 0):.6g}, "
                f"q_min={s.get('quality_min', 0):.6g}"
            )

    return V, F
