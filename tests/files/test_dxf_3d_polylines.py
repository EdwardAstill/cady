from __future__ import annotations

import pytest

from cady import Polyline3D, Vec3
from cady.errors import ReadError
from cady.files import dxf


def _dxf_entities(*entities: str) -> str:
    return "\n".join(("0", "SECTION", "2", "ENTITIES", *entities, "0", "ENDSEC", "0", "EOF", ""))


def test_read_3d_imports_wire_polyline() -> None:
    result = dxf.parse_dxf_3d(
        _dxf_entities(
            "0",
            "POLYLINE",
            "70",
            "9",
            "0",
            "VERTEX",
            "10",
            "0",
            "20",
            "0",
            "30",
            "0",
            "0",
            "VERTEX",
            "10",
            "1",
            "20",
            "0",
            "30",
            "0.5",
            "0",
            "VERTEX",
            "10",
            "1",
            "20",
            "1",
            "30",
            "1",
            "0",
            "SEQEND",
        )
    )

    assert result.meshes == ()
    assert result.wires == (
        Polyline3D((Vec3(0, 0, 0), Vec3(1, 0, 0.5), Vec3(1, 1, 1)), closed=True),
    )


def test_read_mesh_rejects_wire_only_dxf(tmp_path) -> None:
    path = tmp_path / "wire.dxf"
    path.write_text(
        _dxf_entities(
            "0",
            "POLYLINE",
            "70",
            "8",
            "0",
            "VERTEX",
            "10",
            "0",
            "20",
            "0",
            "30",
            "0",
            "0",
            "VERTEX",
            "10",
            "1",
            "20",
            "0",
            "30",
            "1",
            "0",
            "SEQEND",
        ),
        encoding="ascii",
    )

    with pytest.raises(ReadError, match="no supported mesh"):
        dxf.read_mesh(path)
