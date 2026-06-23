from __future__ import annotations

from dataclasses import dataclass
from math import radians
from pathlib import Path

from cady.domain.drawing import SUPPORTED_LINETYPES, DxfDrawing
from cady.domain.shapes2d import Arc, Circle, Line, Polyline
from cady.domain.vec import Vec2
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
)


@dataclass(frozen=True, slots=True)
class DxfPair:
    code: int
    value: str


@dataclass(frozen=True, slots=True)
class LayerRecord:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"


def read_dxf(path: str | Path) -> DxfDrawing:
    """Read supported ASCII DXF entities into a cady drawing.

    The reader is deliberately small: it imports LINE, LWPOLYLINE, CIRCLE, ARC,
    TEXT, and MTEXT entities from the ENTITIES section. Unsupported entities are
    skipped.
    """

    return parse_dxf(Path(path).read_text(encoding="ascii"))


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


def _pairs(text: str) -> list[DxfPair]:
    lines = text.splitlines()
    if len(lines) % 2 != 0:
        raise ReadError("malformed DXF: expected group-code/value line pairs")
    pairs: list[DxfPair] = []
    for index in range(0, len(lines), 2):
        try:
            code = int(lines[index].strip())
        except ValueError as exc:
            line_number = index + 1
            raise ReadError(f"malformed DXF: invalid group code on line {line_number}") from exc
        pairs.append(DxfPair(code, lines[index + 1].strip()))
    return pairs


def _sections(pairs: list[DxfPair]) -> list[tuple[str, list[DxfPair]]]:
    sections: list[tuple[str, list[DxfPair]]] = []
    index = 0
    while index < len(pairs):
        pair = pairs[index]
        if pair.code == 0 and pair.value == "SECTION":
            if index + 1 >= len(pairs) or pairs[index + 1].code != 2:
                raise ReadError("malformed DXF: SECTION missing name")
            name = pairs[index + 1].value.upper()
            index += 2
            body: list[DxfPair] = []
            while index < len(pairs):
                if pairs[index].code == 0 and pairs[index].value == "ENDSEC":
                    break
                body.append(pairs[index])
                index += 1
            sections.append((name, body))
        index += 1
    return sections


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


def _entity_chunks(pairs: list[DxfPair]) -> list[tuple[str, list[DxfPair]]]:
    entities: list[tuple[str, list[DxfPair]]] = []
    for section_name, body in _sections(pairs):
        if section_name == "ENTITIES":
            entities.extend(_chunks(body))
    return entities


def _chunks(pairs: list[DxfPair]) -> list[tuple[str, list[DxfPair]]]:
    chunks: list[tuple[str, list[DxfPair]]] = []
    index = 0
    while index < len(pairs):
        pair = pairs[index]
        if pair.code != 0:
            index += 1
            continue
        entity_type = pair.value.upper()
        index += 1
        chunk: list[DxfPair] = []
        while index < len(pairs) and pairs[index].code != 0:
            chunk.append(pairs[index])
            index += 1
        chunks.append((entity_type, chunk))
    return chunks


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


def _to_float(pair: DxfPair) -> float:
    try:
        return float(pair.value)
    except ValueError as exc:
        raise ReadError(f"malformed DXF: invalid number for group code {pair.code}") from exc
