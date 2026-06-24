from __future__ import annotations

from dataclasses import dataclass
from math import radians
from pathlib import Path

from cady.domain.drawing import SUPPORTED_LINETYPES, DxfDrawing
from cady.domain.mesh import Face3D, FacetedMesh, Polyline3D
from cady.domain.shapes2d import Arc, Circle, Line, Polyline
from cady.domain.vec import Vec2, Vec3
from cady.errors import ReadError
from cady.files.dxf.codes import (
    ANGLE_END,
    ANGLE_START,
    COLOR,
    COUNT,
    FLAGS,
    LAYER,
    RADIUS,
    X,
    Y,
    Z,
)
from cady.files.dxf.parser import DxfPair
from cady.files.dxf.parser import chunks as _chunks
from cady.files.dxf.parser import entity_chunks as _entity_chunks
from cady.files.dxf.parser import pairs as _pairs
from cady.files.dxf.parser import sections as _sections


@dataclass(frozen=True, slots=True)
class LayerRecord:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"


@dataclass(frozen=True, slots=True)
class DxfSkippedEntity:
    entity_type: str
    reason: str
    layer: str | None = None


@dataclass(frozen=True, slots=True)
class Dxf3DImportResult:
    meshes: tuple[FacetedMesh, ...] = ()
    wires: tuple[Polyline3D, ...] = ()
    skipped: tuple[DxfSkippedEntity, ...] = ()


def read_dxf(path: str | Path) -> DxfDrawing:
    """Read supported ASCII DXF entities into a cady drawing.

    The reader is deliberately small: it imports LINE, LWPOLYLINE, CIRCLE, ARC,
    TEXT, and MTEXT entities from the ENTITIES section. Unsupported entities are
    skipped.
    """

    return parse_dxf(Path(path).read_text(encoding="ascii"))


def read_3d(path: str | Path) -> Dxf3DImportResult:
    """Read supported faceted and wire 3D geometry from an ASCII DXF file."""

    return parse_dxf_3d(Path(path).read_text(encoding="ascii"))


def read_mesh(path: str | Path) -> FacetedMesh:
    """Read supported faceted 3D DXF geometry and merge it into one mesh."""

    result = read_3d(path)
    if not result.meshes:
        raise ReadError("DXF contained no supported mesh geometry")
    return FacetedMesh.merged(result.meshes)


def parse_dxf(text: str) -> DxfDrawing:
    """Parse supported ASCII DXF text into a cady drawing."""

    pairs = _pairs(text)
    layers = _layer_records(pairs)
    drawing = DxfDrawing()
    for record in layers.values():
        drawing.layer(record.name, record.color, record.linetype)
    for entity_type, chunk in _entity_chunks(pairs):
        _add_entity(drawing, layers, entity_type, chunk)
    return drawing


def parse_dxf_3d(text: str) -> Dxf3DImportResult:
    """Parse supported faceted and wire 3D geometry from ASCII DXF text."""

    chunks = _entity_chunks(_pairs(text))
    meshes: list[FacetedMesh] = []
    wires: list[Polyline3D] = []
    skipped: list[DxfSkippedEntity] = []
    index = 0
    while index < len(chunks):
        entity_type, chunk = chunks[index]
        if entity_type == "3DFACE":
            meshes.append(_mesh_from_3dface(chunk))
            index += 1
            continue
        if entity_type == "POLYLINE":
            index, polyline_mesh, polyline_wire, polyline_skipped = _read_polyline_3d(
                chunks,
                index,
            )
            if polyline_mesh is not None:
                meshes.append(polyline_mesh)
            if polyline_wire is not None:
                wires.append(polyline_wire)
            if polyline_skipped is not None:
                skipped.append(polyline_skipped)
            continue
        if entity_type in {"3DSOLID", "BODY", "REGION", "SURFACE"}:
            skipped.append(
                DxfSkippedEntity(
                    entity_type,
                    "ACIS-backed solid/surface entities are not supported",
                    _layer_name(chunk),
                )
            )
        elif entity_type == "MESH":
            skipped.append(
                DxfSkippedEntity(entity_type, "MESH entities are not supported", _layer_name(chunk))
            )
        index += 1
    return Dxf3DImportResult(tuple(meshes), tuple(wires), tuple(skipped))


def _layer_records(pairs: list[DxfPair]) -> dict[str, LayerRecord]:
    records: dict[str, LayerRecord] = {}
    for section_name, body in _sections(pairs):
        if section_name != "TABLES":
            continue
        for entity_type, chunk in _chunks(body):
            if entity_type != "LAYER":
                continue
            name = _string(chunk, 2, "0")
            linetype = _string(chunk, 6, "CONTINUOUS").upper()
            if linetype not in SUPPORTED_LINETYPES:
                linetype = "CONTINUOUS"
            records[name] = LayerRecord(
                name=name,
                color=_int(chunk, COLOR, 7),
                linetype=linetype,
            )
    return records
def _add_entity(
    drawing: DxfDrawing,
    layers: dict[str, LayerRecord],
    entity_type: str,
    chunk: list[DxfPair],
) -> None:
    if entity_type in {"TEXT", "MTEXT"}:
        drawing.add_text(
            _text(chunk),
            (_float(chunk, X), _float(chunk, Y)),
            _float(chunk, 40, 0.1),
            _layer_name(chunk),
        )
        return

    shape = _shape(entity_type, chunk)
    if shape is None:
        return
    layer_name = _layer_name(chunk)
    record = layers.get(layer_name, LayerRecord(layer_name))
    drawing.layer(record.name, record.color, record.linetype).add(shape)


def _shape(entity_type: str, chunk: list[DxfPair]) -> Line | Polyline | Circle | Arc | None:
    if entity_type == "LINE":
        return Line(
            Vec2(_float(chunk, X), _float(chunk, Y)),
            Vec2(_float(chunk, 11), _float(chunk, 21)),
        )
    if entity_type == "LWPOLYLINE":
        vertices = _lwpolyline_vertices(chunk)
        if len(vertices) < 2:
            return None
        closed = bool(_int(chunk, FLAGS, 0) & 1)
        return Polyline(vertices, closed=closed)
    if entity_type == "CIRCLE":
        return Circle(Vec2(_float(chunk, X), _float(chunk, Y)), _float(chunk, RADIUS))
    if entity_type == "ARC":
        return Arc(
            Vec2(_float(chunk, X), _float(chunk, Y)),
            _float(chunk, RADIUS),
            radians(_float(chunk, ANGLE_START)),
            radians(_float(chunk, ANGLE_END)),
        )
    return None


def _lwpolyline_vertices(chunk: list[DxfPair]) -> tuple[Vec2, ...]:
    vertices: list[Vec2] = []
    pending_x: float | None = None
    for pair in chunk:
        if pair.code == X:
            pending_x = _to_float(pair)
        elif pair.code == Y and pending_x is not None:
            vertices.append(Vec2(pending_x, _to_float(pair)))
            pending_x = None
    expected_count = _maybe_int(chunk, COUNT)
    if expected_count is not None and expected_count != len(vertices):
        raise ReadError(
            f"malformed DXF: LWPOLYLINE expected {expected_count} vertices, "
            f"found {len(vertices)}"
        )
    return tuple(vertices)


def _mesh_from_3dface(chunk: list[DxfPair]) -> FacetedMesh:
    p1 = _vec3(chunk, X, Y, Z)
    p2 = _vec3(chunk, 11, 21, 31)
    p3 = _vec3(chunk, 12, 22, 32)
    p4 = _maybe_vec3(chunk, 13, 23, 33)
    vertices = (p1, p2, p3)
    if p4 is not None and p4 != p3:
        vertices = vertices + (p4,)
    return FacetedMesh.from_faces((Face3D(vertices),))


def _read_polyline_3d(
    chunks: list[tuple[str, list[DxfPair]]],
    start_index: int,
) -> tuple[int, FacetedMesh | None, Polyline3D | None, DxfSkippedEntity | None]:
    entity_type, header = chunks[start_index]
    if entity_type != "POLYLINE":
        raise ReadError("internal DXF parser error: expected POLYLINE chunk")

    vertices: list[list[DxfPair]] = []
    index = start_index + 1
    while index < len(chunks):
        child_type, child_chunk = chunks[index]
        if child_type == "SEQEND":
            next_index = index + 1
            break
        if child_type == "VERTEX":
            vertices.append(child_chunk)
        index += 1
    else:
        raise ReadError("malformed DXF: POLYLINE missing SEQEND")

    flags = _int(header, FLAGS, 0)
    if flags & 64:
        return (
            next_index,
            _polyface_mesh(header, vertices),
            None,
            None,
        )

    points = tuple(_vec3(vertex, X, Y, Z, default_z=0.0) for vertex in vertices)
    is_3d = bool(flags & 8) or any(point.z != 0 for point in points)
    if not is_3d:
        return (next_index, None, None, None)
    if not points:
        return (
            next_index,
            None,
            None,
            DxfSkippedEntity("POLYLINE", "3D POLYLINE contains no vertices", _layer_name(header)),
        )
    return (next_index, None, Polyline3D(points, closed=bool(flags & 1)), None)


def _polyface_mesh(header: list[DxfPair], vertices: list[list[DxfPair]]) -> FacetedMesh:
    points: list[Vec3] = []
    faces: list[tuple[int, int, int]] = []
    for vertex in vertices:
        vertex_flags = _int(vertex, FLAGS, 0)
        if vertex_flags & 128:
            indices = tuple(
                abs(value) - 1
                for value in (
                    _int(vertex, 71, 0),
                    _int(vertex, 72, 0),
                    _int(vertex, 73, 0),
                    _int(vertex, 74, 0),
                )
                if value != 0
            )
            if len(indices) < 3:
                raise ReadError("malformed DXF: polyface face record has fewer than 3 indices")
            for index in indices:
                if index < 0 or index >= len(points):
                    raise ReadError("malformed DXF: polyface face index out of range")
            first = indices[0]
            faces.extend(
                (first, indices[index], indices[index + 1])
                for index in range(1, len(indices) - 1)
            )
            continue
        points.append(_vec3(vertex, X, Y, Z, default_z=0.0))

    if not faces:
        raise ReadError(
            f"malformed DXF: polyface POLYLINE on layer {_layer_name(header)!r} "
            "contains no face records"
        )
    return FacetedMesh(tuple(points), tuple(faces))


def _layer_name(chunk: list[DxfPair]) -> str:
    return _string(chunk, LAYER, "0")


def _text(chunk: list[DxfPair]) -> str:
    return "\n".join(pair.value for pair in chunk if pair.code in {1, 3})


def _string(chunk: list[DxfPair], code: int, default: str) -> str:
    for pair in chunk:
        if pair.code == code:
            return pair.value
    return default


def _float(chunk: list[DxfPair], code: int, default: float | None = None) -> float:
    for pair in chunk:
        if pair.code == code:
            return _to_float(pair)
    if default is not None:
        return default
    raise ReadError(f"malformed DXF: missing group code {code}")


def _int(chunk: list[DxfPair], code: int, default: int) -> int:
    value = _maybe_int(chunk, code)
    return default if value is None else value


def _maybe_int(chunk: list[DxfPair], code: int) -> int | None:
    for pair in chunk:
        if pair.code != code:
            continue
        try:
            return int(pair.value)
        except ValueError as exc:
            raise ReadError(f"malformed DXF: invalid integer for group code {code}") from exc
    return None


def _vec3(
    chunk: list[DxfPair],
    x_code: int,
    y_code: int,
    z_code: int,
    *,
    default_z: float | None = None,
) -> Vec3:
    return Vec3(
        _float(chunk, x_code),
        _float(chunk, y_code),
        _float(chunk, z_code, default_z) if default_z is not None else _float(chunk, z_code),
    )


def _maybe_vec3(
    chunk: list[DxfPair],
    x_code: int,
    y_code: int,
    z_code: int,
) -> Vec3 | None:
    x = _maybe_float(chunk, x_code)
    y = _maybe_float(chunk, y_code)
    z = _maybe_float(chunk, z_code)
    if x is None and y is None and z is None:
        return None
    if x is None or y is None or z is None:
        raise ReadError(f"malformed DXF: incomplete 3D point at group code {x_code}")
    return Vec3(x, y, z)


def _maybe_float(chunk: list[DxfPair], code: int) -> float | None:
    for pair in chunk:
        if pair.code == code:
            return _to_float(pair)
    return None


def _to_float(pair: DxfPair) -> float:
    try:
        return float(pair.value)
    except ValueError as exc:
        raise ReadError(f"malformed DXF: invalid number for group code {pair.code}") from exc
