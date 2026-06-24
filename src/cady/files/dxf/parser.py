from __future__ import annotations

from dataclasses import dataclass

from cady.errors import ReadError


@dataclass(frozen=True, slots=True)
class DxfPair:
    code: int
    value: str


def pairs(text: str) -> list[DxfPair]:
    lines = text.splitlines()
    if len(lines) % 2 != 0:
        raise ReadError("malformed DXF: expected group-code/value line pairs")
    parsed: list[DxfPair] = []
    for index in range(0, len(lines), 2):
        try:
            code = int(lines[index].strip())
        except ValueError as exc:
            line_number = index + 1
            raise ReadError(f"malformed DXF: invalid group code on line {line_number}") from exc
        parsed.append(DxfPair(code, lines[index + 1].strip()))
    return parsed


def sections(parsed_pairs: list[DxfPair]) -> list[tuple[str, list[DxfPair]]]:
    found: list[tuple[str, list[DxfPair]]] = []
    index = 0
    while index < len(parsed_pairs):
        pair = parsed_pairs[index]
        if pair.code == 0 and pair.value == "SECTION":
            if index + 1 >= len(parsed_pairs) or parsed_pairs[index + 1].code != 2:
                raise ReadError("malformed DXF: SECTION missing name")
            name = parsed_pairs[index + 1].value.upper()
            index += 2
            body: list[DxfPair] = []
            while index < len(parsed_pairs):
                if parsed_pairs[index].code == 0 and parsed_pairs[index].value == "ENDSEC":
                    break
                body.append(parsed_pairs[index])
                index += 1
            found.append((name, body))
        index += 1
    return found


def chunks(parsed_pairs: list[DxfPair]) -> list[tuple[str, list[DxfPair]]]:
    found: list[tuple[str, list[DxfPair]]] = []
    index = 0
    while index < len(parsed_pairs):
        pair = parsed_pairs[index]
        if pair.code != 0:
            index += 1
            continue
        entity_type = pair.value.upper()
        index += 1
        chunk: list[DxfPair] = []
        while index < len(parsed_pairs) and parsed_pairs[index].code != 0:
            chunk.append(parsed_pairs[index])
            index += 1
        found.append((entity_type, chunk))
    return found


def entity_chunks(parsed_pairs: list[DxfPair]) -> list[tuple[str, list[DxfPair]]]:
    entities: list[tuple[str, list[DxfPair]]] = []
    for section_name, body in sections(parsed_pairs):
        if section_name == "ENTITIES":
            entities.extend(chunks(body))
    return entities
