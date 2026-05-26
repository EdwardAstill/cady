from __future__ import annotations

import pytest

from cady import DxfDrawing, SceneError, StlMesh, circle, line, prism, sphere


def test_dxf_layers_and_chaining() -> None:
    d = DxfDrawing()
    d.layer("PLATE", 7)
    d.layer("HOLES", 1)
    assert len(d.layers) == 2
    assert d.layers["HOLES"].color == 1
    layer = d.layer("PLATE", 7).add(line((0, 0), (1, 0))).add(line((1, 0), (1, 1)))
    assert layer is d.layers["PLATE"]
    assert len(layer.entities) == 2


def test_dxf_existing_layer_keeps_first_linetype() -> None:
    d = DxfDrawing()
    layer = d.layer("CENTERLINES", color=3, linetype="CENTER")
    assert d.layer("CENTERLINES", color=7, linetype="HIDDEN") is layer
    assert d.layers["CENTERLINES"].color == 3
    assert d.layers["CENTERLINES"].linetype == "CENTER"


def test_dxf_rejects_3d() -> None:
    with pytest.raises(SceneError):
        DxfDrawing().layer("X").add(sphere((0, 0, 0), 1))  # type: ignore[arg-type]


def test_dxf_text_and_dimension_chaining() -> None:
    d = DxfDrawing().add_text("LABEL", at=(0, 0), height=0.01, layer="TEXT")
    assert d.texts[0].text == "LABEL"
    assert d.add_dimension((0, 0), (1, 0), offset=0.1) is d
    assert d.dimensions[0].kind == "aligned"


def test_stl_mesh_chains_and_rejects_2d(tmp_path) -> None:
    mesh = StlMesh().add(prism((0, 0, 0), (2, 2, 1)))
    path = tmp_path / "x.stl"
    assert mesh.write(path) is mesh
    assert path.stat().st_size > 0
    with pytest.raises(SceneError):
        StlMesh().add(circle((0, 0), 1))  # type: ignore[arg-type]
