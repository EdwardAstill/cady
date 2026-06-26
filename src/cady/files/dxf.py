from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import degrees, dist, radians
from pathlib import Path
from typing import cast

from cady.drawing import Drawing2D, DrawingEntity, Text2D
from cady.errors import ReadError, WriteError
from cady.geometry import Arc2D, Circle2D, ClosedPolyline2D, Line2D, Mesh3D, Polyline2D, Wireframe3D
from cady.vec import Vec2, Vec3

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class DxfSkippedEntity:
    entity_type: str
    reason: str
    layer: str | None = None


@dataclass(frozen=True, slots=True)
class DxfImportResult:
    drawing: Drawing2D | None = None
    meshes: tuple[Mesh3D, ...] = ()
    wireframes: tuple[Wireframe3D, ...] = ()
    curves: tuple[DxfWireCurve, ...] = ()
    skipped: tuple[DxfSkippedEntity, ...] = ()


@dataclass(frozen=True, slots=True)
class DxfWireCurve:
    vertices: tuple[Vec3, ...]
    edges: tuple[tuple[int, int], ...]
    layer: str
    entity_type: str
    source_index: int

    @property
    def constant_x(self) -> bool:
        return _is_constant(tuple(point.x for point in self.vertices))

    @property
    def constant_y(self) -> bool:
        return _is_constant(tuple(point.y for point in self.vertices))

    @property
    def constant_z(self) -> bool:
        return _is_constant(tuple(point.z for point in self.vertices))


@dataclass(frozen=True, slots=True)
class _Pair:
    code: int
    value: str


def read(path: str | Path) -> DxfImportResult:
    text = Path(path).read_text(encoding="ascii")
    pairs = _pairs(text)
    drawing = _parse_drawing(pairs)
    meshes, wireframes, curves, skipped = _parse_meshes(pairs)
    return DxfImportResult(
        drawing=drawing if drawing.entities else None,
        meshes=meshes,
        wireframes=wireframes,
        curves=curves,
        skipped=skipped,
    )


def read_drawing(path: str | Path) -> Drawing2D:
    result = read(path)
    if result.drawing is None:
        raise ReadError("DXF contained no supported 2D drawing entities")
    return result.drawing


def read_mesh(
    path: str | Path,
    *,
    mirror_origin: object | None = None,
    mirror_normal: object | None = None,
    close_origin: object | None = None,
    close_normal: object | None = None,
    tolerance: float = 1e-3,
    max_distance: float | None = None,
) -> Mesh3D:
    result = read(path)
    if _line_mesh_requested(
        mirror_origin=mirror_origin,
        mirror_normal=mirror_normal,
        close_origin=close_origin,
        close_normal=close_normal,
        max_distance=max_distance,
    ):
        raise ReadError("read_mesh no longer converts DXF line geometry to mesh faces")
    if not result.meshes:
        raise ReadError("DXF contained no supported mesh geometry")
    return Mesh3D.merged(result.meshes)


def read_curves(path: str | Path) -> tuple[DxfWireCurve, ...]:
    return read(path).curves


def read_wireframe(path: str | Path) -> Wireframe3D:
    result = read(path)
    if not result.wireframes:
        raise ReadError("DXF contained no supported 3D wire geometry")
    return _merge_wireframes(result.wireframes)


def _merge_wireframes(wireframes: Iterable[Wireframe3D]) -> Wireframe3D:
    vertices: list[Vec3] = []
    edges: list[tuple[int, int]] = []
    offset = 0
    for wf in wireframes:
        vertices.extend(wf.vertices)
        edges.extend((a + offset, b + offset) for a, b in wf.edges)
        offset += len(wf.vertices)
    return Wireframe3D(tuple(vertices), tuple(edges))


def _line_mesh_requested(
    *,
    mirror_origin: object | None,
    mirror_normal: object | None,
    close_origin: object | None,
    close_normal: object | None,
    max_distance: float | None,
) -> bool:
    return any(
        value is not None
        for value in (
            mirror_origin,
            mirror_normal,
            close_origin,
            close_normal,
            max_distance,
        )
    )


def _mesh_from_line_geometry(  # pyright: ignore[reportUnusedFunction]
    wireframes: tuple[Wireframe3D, ...],
    *,
    mirror_origin: object | None,
    mirror_normal: object | None,
    close_origin: object | None,
    close_normal: object | None,
    tolerance: float,
    max_distance: float | None,
) -> Mesh3D:
    if (mirror_origin is None) != (mirror_normal is None):
        raise ValueError("mirror_origin and mirror_normal must be provided together")
    has_close_plane = (
        close_origin is not None or close_normal is not None or max_distance is not None
    )
    if has_close_plane and (
        close_origin is None or close_normal is None or max_distance is None
    ):
        raise ValueError(
            "line-geometry mesh conversion requires close_origin, close_normal, "
            "and max_distance"
        )
    if not wireframes:
        raise ReadError("DXF contained no supported line geometry for mesh conversion")

    if not has_close_plane:
        mesh = _loft_section_wireframes_to_mesh(wireframes, tolerance=tolerance)
        if mesh is None:
            raise ReadError("DXF line geometry could not be converted to mesh faces")
        mesh = _mesh_with_wireframe_display_edges(mesh, wireframes)
        if mirror_origin is not None and mirror_normal is not None:
            mesh = mesh.mirror(mirror_origin, mirror_normal)
        return mesh
    assert close_origin is not None
    assert close_normal is not None
    assert max_distance is not None
    wireframe = _merge_wireframes(wireframes)
    if mirror_origin is not None and mirror_normal is not None:
        wireframe = wireframe.mirror(mirror_origin, mirror_normal)
    mesh = Mesh3D(wireframe.vertices, (), wireframe.edges).close_to_plane(
        close_origin,
        close_normal,
        tolerance=tolerance,
        max_distance=max_distance,
    )
    return Mesh3D(mesh.vertices, mesh.faces)


def _loft_section_wireframes_to_mesh(
    wireframes: tuple[Wireframe3D, ...],
    *,
    tolerance: float,
) -> Mesh3D | None:
    sections = _section_curves(wireframes, tolerance=tolerance)
    if len(sections) < 2:
        return None

    sample_count = min(max(len(vertices) for _x, vertices in sections), 96)
    if sample_count < 2:
        return None

    rows = tuple(
        _resample_polyline(_orient_section(vertices), sample_count)
        for _x, vertices in sections
    )
    vertices = tuple(point for row in rows for point in row)
    faces: list[tuple[int, int, int]] = []
    edges: set[tuple[int, int]] = set()

    for section_index in range(len(rows)):
        row_start = section_index * sample_count
        for sample_index in range(sample_count - 1):
            edges.add((row_start + sample_index, row_start + sample_index + 1))

    for section_index in range(len(rows) - 1):
        left_start = section_index * sample_count
        right_start = (section_index + 1) * sample_count
        for sample_index in range(sample_count):
            edges.add((left_start + sample_index, right_start + sample_index))
        for sample_index in range(sample_count - 1):
            a = left_start + sample_index
            b = right_start + sample_index
            c = left_start + sample_index + 1
            d = right_start + sample_index + 1
            _append_face_if_valid(faces, vertices, (a, b, d), tolerance)
            _append_face_if_valid(faces, vertices, (a, d, c), tolerance)

    if not faces:
        return None
    return Mesh3D(vertices, tuple(faces), tuple(sorted(edges)))


def _mesh_with_wireframe_display_edges(
    mesh: Mesh3D,
    wireframes: tuple[Wireframe3D, ...],
) -> Mesh3D:
    vertices = list(mesh.vertices)
    edges = list(mesh.edges)
    offset = len(vertices)
    for wireframe in wireframes:
        vertices.extend(wireframe.vertices)
        edges.extend((a + offset, b + offset) for a, b in wireframe.edges)
        offset += len(wireframe.vertices)
    return Mesh3D(tuple(vertices), mesh.faces, tuple(edges))


def _section_curves(
    wireframes: tuple[Wireframe3D, ...],
    *,
    tolerance: float,
) -> tuple[tuple[float, tuple[Vec3, ...]], ...]:
    x_tolerance = max(tolerance, 1e-3)
    grouped: dict[int, list[tuple[float, tuple[Vec3, ...]]]] = {}
    for wireframe in wireframes:
        vertices = wireframe.vertices
        if len(vertices) < 4:
            continue
        xs = [point.x for point in vertices]
        ys = [point.y for point in vertices]
        zs = [point.z for point in vertices]
        if max(xs) - min(xs) > x_tolerance:
            continue
        if max(ys) - min(ys) <= x_tolerance or max(zs) - min(zs) <= x_tolerance:
            continue
        length = _polyline_length(vertices)
        if length <= x_tolerance:
            continue
        x = sum(xs) / len(xs)
        grouped.setdefault(round(x / x_tolerance), []).append((length, vertices))

    sections: list[tuple[float, tuple[Vec3, ...]]] = []
    for group in grouped.values():
        _length, vertices = max(group, key=lambda item: item[0])
        x = sum(point.x for point in vertices) / len(vertices)
        sections.append((x, vertices))
    return tuple(sorted(sections, key=lambda item: item[0]))


def _orient_section(vertices: tuple[Vec3, ...]) -> tuple[Vec3, ...]:
    if vertices[0].z > vertices[-1].z:
        return tuple(reversed(vertices))
    return vertices


def _resample_polyline(vertices: tuple[Vec3, ...], count: int) -> tuple[Vec3, ...]:
    if count < 2:
        raise ValueError("count must be at least 2")
    distances = [0.0]
    for previous, current in zip(vertices, vertices[1:], strict=False):
        distances.append(distances[-1] + dist(previous.tuple(), current.tuple()))
    total = distances[-1]
    if total == 0.0:
        return tuple(vertices[0] for _ in range(count))

    sampled: list[Vec3] = []
    segment_index = 0
    for sample_index in range(count):
        target = total * sample_index / (count - 1)
        while segment_index < len(distances) - 2 and distances[segment_index + 1] < target:
            segment_index += 1
        start = vertices[segment_index]
        end = vertices[segment_index + 1]
        start_distance = distances[segment_index]
        segment_length = distances[segment_index + 1] - start_distance
        ratio = 0.0 if segment_length == 0.0 else (target - start_distance) / segment_length
        sampled.append(
            Vec3(
                start.x + (end.x - start.x) * ratio,
                start.y + (end.y - start.y) * ratio,
                start.z + (end.z - start.z) * ratio,
            )
        )
    return tuple(sampled)


def _polyline_length(vertices: tuple[Vec3, ...]) -> float:
    return sum(
        dist(previous.tuple(), current.tuple())
        for previous, current in zip(vertices, vertices[1:], strict=False)
    )


def _append_face_if_valid(
    faces: list[tuple[int, int, int]],
    vertices: tuple[Vec3, ...],
    face: tuple[int, int, int],
    tolerance: float,
) -> None:
    a, b, c = (vertices[index] for index in face)
    if (
        dist(a.tuple(), b.tuple()) <= tolerance
        or dist(b.tuple(), c.tuple()) <= tolerance
        or dist(c.tuple(), a.tuple()) <= tolerance
    ):
        return
    faces.append(face)


def render(drawing: Drawing2D, *, tolerance: float = 1e-3) -> str:
    if tolerance <= 0:
        raise WriteError("tolerance must be positive")
    if not drawing.entities:
        raise WriteError("cannot write empty DXF drawing")
    layer_names = tuple(layer.name for layer in drawing.layers) or ("0",)
    lines: list[str] = [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$ACADVER",
        "1",
        "AC1032",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "TABLES",
        "0",
        "TABLE",
        "2",
        "LAYER",
        "70",
        str(len(layer_names)),
    ]
    for layer in drawing.layers:
        lines.extend(
            [
                "0",
                "LAYER",
                "2",
                layer.name,
                "70",
                "0",
                "62",
                str(layer.color),
                "6",
                layer.linetype,
            ]
        )
    lines.extend(["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"])
    for item in drawing.entities:
        lines.extend(_entity_lines(item, tolerance=tolerance))
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(lines) + "\n"


def write(drawing: Drawing2D, path: str | Path, *, tolerance: float = 1e-3) -> Drawing2D:
    Path(path).write_text(render(drawing, tolerance=tolerance), encoding="ascii")
    return drawing


def _entity_lines(item: object, *, tolerance: float) -> list[str]:
    if isinstance(item, DrawingEntity):
        return _geometry_lines(item.geometry, item.layer, tolerance=tolerance)
    if isinstance(item, Text2D):
        x, y = item.at
        return [
            "0",
            "TEXT",
            "8",
            item.layer,
            "10",
            _f(x),
            "20",
            _f(y),
            "40",
            _f(item.height),
            "1",
            item.text,
        ]
    return []


def _geometry_lines(geometry: object, layer: str, *, tolerance: float) -> list[str]:
    if isinstance(geometry, Line2D):
        return [
            "0",
            "LINE",
            "8",
            layer,
            "10",
            _f(geometry.start.x),
            "20",
            _f(geometry.start.y),
            "11",
            _f(geometry.end.x),
            "21",
            _f(geometry.end.y),
        ]
    if isinstance(geometry, Polyline2D | ClosedPolyline2D):
        vertices = geometry.vertices
        closed = isinstance(geometry, ClosedPolyline2D)
        return _lwpolyline_lines(vertices, layer, closed=closed)
    if isinstance(geometry, Circle2D):
        return [
            "0",
            "CIRCLE",
            "8",
            layer,
            "10",
            _f(geometry.centre.x),
            "20",
            _f(geometry.centre.y),
            "40",
            _f(geometry.radius),
        ]
    if isinstance(geometry, Arc2D):
        return [
            "0",
            "ARC",
            "8",
            layer,
            "10",
            _f(geometry.centre.x),
            "20",
            _f(geometry.centre.y),
            "40",
            _f(geometry.radius),
            "50",
            _f(degrees(geometry.start_rad)),
            "51",
            _f(degrees(geometry.end_rad)),
        ]
    to_array = getattr(geometry, "to_array", None)
    if callable(to_array):
        polygon = to_array(tolerance=tolerance)
        outer = _point2_sequence(getattr(polygon, "outer", ()))
        return _lwpolyline_lines(outer, layer, closed=True)
    return []


def _lwpolyline_lines(
    vertices: Iterable[Point2] | Iterable[object],
    layer: str,
    *,
    closed: bool,
) -> list[str]:
    raw = tuple(vertices)
    lines = [
        "0",
        "LWPOLYLINE",
        "8",
        layer,
        "90",
        str(len(raw)),
        "70",
        "1" if closed else "0",
    ]
    for point in raw:
        x, y = _point2(point)
        lines.extend(["10", _f(x), "20", _f(y)])
    return lines


def _parse_drawing(pairs: tuple[_Pair, ...]) -> Drawing2D:
    drawing = Drawing2D()
    for entity_type, chunk in _entity_chunks(pairs):
        layer = _string(chunk, 8, "0")
        if entity_type == "LINE":
            drawing = drawing.add(
                Line2D(
                    (_float(chunk, 10), _float(chunk, 20)),
                    (_float(chunk, 11), _float(chunk, 21)),
                ),
                layer=layer,
            )
        elif entity_type == "LWPOLYLINE":
            points = _lwpolyline_points(chunk)
            if len(points) >= 2:
                closed = bool(_int(chunk, 70, 0) & 1)
                geometry = ClosedPolyline2D(points) if closed else Polyline2D(points)
                drawing = drawing.add(geometry, layer=layer)
        elif entity_type == "CIRCLE":
            drawing = drawing.add(
                Circle2D((_float(chunk, 10), _float(chunk, 20)), _float(chunk, 40)),
                layer=layer,
            )
        elif entity_type == "ARC":
            drawing = drawing.add(
                Arc2D(
                    (_float(chunk, 10), _float(chunk, 20)),
                    _float(chunk, 40),
                    radians(_float(chunk, 50)),
                    radians(_float(chunk, 51)),
                ),
                layer=layer,
            )
        elif entity_type in {"TEXT", "MTEXT"}:
            drawing = drawing.add_text(
                _string(chunk, 1, ""),
                at=(_float(chunk, 10), _float(chunk, 20)),
                height=_float(chunk, 40, 0.1),
                layer=layer,
            )
    return drawing


def _parse_meshes(
    pairs: tuple[_Pair, ...],
) -> tuple[
    tuple[Mesh3D, ...],
    tuple[Wireframe3D, ...],
    tuple[DxfWireCurve, ...],
    tuple[DxfSkippedEntity, ...],
]:
    meshes: list[Mesh3D] = []
    wireframes: list[Wireframe3D] = []
    curves: list[DxfWireCurve] = []
    skipped: list[DxfSkippedEntity] = []
    chunks = _entity_chunks(pairs)
    index = 0
    while index < len(chunks):
        entity_type, chunk = chunks[index]
        if entity_type == "3DFACE":
            meshes.append(_mesh_from_3dface(chunk))
        elif entity_type == "POLYLINE":
            vertices: list[Vec3] = []
            layer = _string(chunk, 8, None)
            index += 1
            while index < len(chunks) and chunks[index][0] != "SEQEND":
                child_type, child = chunks[index]
                if child_type == "VERTEX":
                    vertices.append(_vec3(child, 10, 20, 30))
                index += 1
            if len(vertices) >= 2:
                edges = tuple((i, i + 1) for i in range(len(vertices) - 1))
                curve = DxfWireCurve(
                    tuple(vertices),
                    edges,
                    layer,
                    entity_type,
                    len(curves),
                )
                curves.append(curve)
                wireframes.append(Wireframe3D(curve.vertices, curve.edges))
            else:
                skipped.append(
                    DxfSkippedEntity(
                        entity_type,
                        "polyline has fewer than two vertices",
                        layer,
                    )
                )
        elif entity_type in {"3DSOLID", "BODY", "REGION", "SURFACE"}:
            skipped.append(
                DxfSkippedEntity(
                    entity_type,
                    "ACIS-backed solid/surface entities are not supported",
                    _string(chunk, 8, None),
                )
            )
        index += 1
    return tuple(meshes), tuple(wireframes), tuple(curves), tuple(skipped)


def _mesh_from_3dface(chunk: tuple[_Pair, ...]) -> Mesh3D:
    p1 = _vec3(chunk, 10, 20, 30)
    p2 = _vec3(chunk, 11, 21, 31)
    p3 = _vec3(chunk, 12, 22, 32)
    p4 = _maybe_vec3(chunk, 13, 23, 33)
    vertices = (p1, p2, p3)
    faces = ((0, 1, 2),)
    if p4 is not None and p4 != p3:
        vertices = (p1, p2, p3, p4)
        faces = ((0, 1, 2), (0, 2, 3))
    return Mesh3D(vertices, faces)


def _pairs(text: str) -> tuple[_Pair, ...]:
    lines = text.splitlines()
    if len(lines) % 2 != 0:
        raise ReadError("malformed DXF: expected group-code/value line pairs")
    parsed: list[_Pair] = []
    for index in range(0, len(lines), 2):
        try:
            code = int(lines[index].strip())
        except ValueError as exc:
            raise ReadError(f"malformed DXF: invalid group code on line {index + 1}") from exc
        parsed.append(_Pair(code, lines[index + 1].strip()))
    return tuple(parsed)


def _entity_chunks(pairs: tuple[_Pair, ...]) -> tuple[tuple[str, tuple[_Pair, ...]], ...]:
    chunks: list[tuple[str, tuple[_Pair, ...]]] = []
    for section_name, section_pairs in _sections(pairs):
        if section_name != "ENTITIES":
            continue
        chunks.extend(_chunks(section_pairs))
    return tuple(chunks)


def _sections(pairs: tuple[_Pair, ...]) -> tuple[tuple[str, tuple[_Pair, ...]], ...]:
    sections: list[tuple[str, tuple[_Pair, ...]]] = []
    index = 0
    while index < len(pairs):
        pair = pairs[index]
        if pair.code == 0 and pair.value == "SECTION":
            if index + 1 >= len(pairs) or pairs[index + 1].code != 2:
                raise ReadError("malformed DXF: SECTION missing name")
            name = pairs[index + 1].value.upper()
            index += 2
            body: list[_Pair] = []
            while index < len(pairs):
                if pairs[index].code == 0 and pairs[index].value == "ENDSEC":
                    break
                body.append(pairs[index])
                index += 1
            sections.append((name, tuple(body)))
        index += 1
    return tuple(sections)


def _chunks(pairs: tuple[_Pair, ...]) -> tuple[tuple[str, tuple[_Pair, ...]], ...]:
    chunks: list[tuple[str, tuple[_Pair, ...]]] = []
    index = 0
    while index < len(pairs):
        if pairs[index].code != 0:
            index += 1
            continue
        entity_type = pairs[index].value.upper()
        index += 1
        chunk: list[_Pair] = []
        while index < len(pairs) and pairs[index].code != 0:
            chunk.append(pairs[index])
            index += 1
        chunks.append((entity_type, tuple(chunk)))
    return tuple(chunks)


def _lwpolyline_points(chunk: tuple[_Pair, ...]) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    pending_x: float | None = None
    for pair in chunk:
        if pair.code == 10:
            pending_x = float(pair.value)
        elif pair.code == 20 and pending_x is not None:
            points.append((pending_x, float(pair.value)))
            pending_x = None
    return tuple(points)


def _vec3(chunk: tuple[_Pair, ...], x: int, y: int, z: int) -> Vec3:
    return Vec3(_float(chunk, x), _float(chunk, y), _float(chunk, z, 0.0))


def _maybe_vec3(chunk: tuple[_Pair, ...], x: int, y: int, z: int) -> Vec3 | None:
    if _maybe_float(chunk, x) is None or _maybe_float(chunk, y) is None:
        return None
    return _vec3(chunk, x, y, z)


def _string(chunk: tuple[_Pair, ...], code: int, default: str | None = "") -> str:
    for pair in chunk:
        if pair.code == code:
            return pair.value
    if default is None:
        return ""
    return default


def _int(chunk: tuple[_Pair, ...], code: int, default: int = 0) -> int:
    for pair in chunk:
        if pair.code == code:
            return int(pair.value)
    return default


def _float(chunk: tuple[_Pair, ...], code: int, default: float = 0.0) -> float:
    value = _maybe_float(chunk, code)
    return default if value is None else value


def _maybe_float(chunk: tuple[_Pair, ...], code: int) -> float | None:
    for pair in chunk:
        if pair.code == code:
            return float(pair.value)
    return None


def _point2_sequence(values: object) -> tuple[Point2, ...]:
    return tuple(_point2(value) for value in values)  # type: ignore[reportUnknownVariableType]


def _point2(value: object) -> Point2:
    if isinstance(value, Vec2):
        return (value.x, value.y)
    try:
        raw = tuple(cast(Iterable[object], value))
    except (TypeError, ValueError) as exc:
        raise WriteError("expected 2D point values") from exc
    if len(raw) != 2:
        raise WriteError("expected 2D point values")
    x = cast(float | int | str, raw[0])
    y = cast(float | int | str, raw[1])
    return (float(x), float(y))


def _f(value: float) -> str:
    return f"{float(value):.12g}"


def _is_constant(values: tuple[float, ...], *, tolerance: float = 1e-9) -> bool:
    if not values:
        return False
    return max(values) - min(values) <= tolerance


__all__ = [
    "DxfImportResult",
    "DxfSkippedEntity",
    "DxfWireCurve",
    "read",
    "read_curves",
    "read_drawing",
    "read_mesh",
    "read_wireframe",
    "render",
    "write",
]
