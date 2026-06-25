from pathlib import Path

from cady import Drawing2D, Line2D, box
from cady.files import dxf, step, stl
from cady.geometry3d import Mesh3D
from cady.vec import Vec3


def test_dxf_write_and_read_drawing(tmp_path: Path) -> None:
    drawing = Drawing2D("front").add(Line2D((0, 0), (1, 0)), layer="CUT")
    path = tmp_path / "front.dxf"

    dxf.write(drawing, path, tolerance=1e-3)

    imported = dxf.read_drawing(path)
    assert imported.entities
    assert imported.entities[0].layer == "CUT"


def test_dxf_read_mesh(tmp_path: Path) -> None:
    path = tmp_path / "mesh.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "3DFACE",
                "10",
                "0",
                "20",
                "0",
                "30",
                "0",
                "11",
                "1",
                "21",
                "0",
                "31",
                "0",
                "12",
                "0",
                "22",
                "1",
                "32",
                "0",
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    mesh = dxf.read_mesh(path)
    assert len(mesh.faces) == 1


def test_dxf_read_polyline_wires(tmp_path: Path) -> None:
    path = tmp_path / "wire.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "POLYLINE",
                "8",
                "WATERLINES",
                "66",
                "1",
                "0",
                "VERTEX",
                "10",
                "0",
                "20",
                "0",
                "30",
                "1",
                "0",
                "VERTEX",
                "10",
                "2",
                "20",
                "0",
                "30",
                "3",
                "0",
                "SEQEND",
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    result = dxf.read(path)

    assert len(result.wireframes) == 1
    assert [point.tuple() for point in result.wireframes[0].vertices] == [
        (0.0, 0.0, 1.0),
        (2.0, 0.0, 3.0),
    ]
    assert result.wireframes[0].edges == ((0, 1),)
    assert not hasattr(result, "wires")


def test_stl_write_mesh(tmp_path: Path) -> None:
    mesh = Mesh3D((Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)), ((0, 1, 2),))
    path = tmp_path / "mesh.stl"

    stl.write(mesh, path, ascii=True, tolerance=1e-3)

    assert path.read_text(encoding="ascii").startswith("solid cady")


def test_step_render_body() -> None:
    text = step.render(box(1, 1, 1), tolerance=1e-3)

    assert "ISO-10303-21" in text
    assert "POLY_LOOP" in text
