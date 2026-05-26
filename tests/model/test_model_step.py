from __future__ import annotations

import pytest

from cady import Model, WriteError, prism, sphere


def test_write_step_prism_creates_file(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))
    result = model.write_step(tmp_path / "demo.step")
    assert result is model
    text = (tmp_path / "demo.step").read_text(encoding="ascii")
    assert "MANIFOLD_SOLID_BREP" in text
    assert "CLOSED_SHELL" in text


def test_write_step_multiple_prisms_in_one_part(tmp_path) -> None:
    model = Model("demo")
    part = model.part("body")
    part.add(prism((0, 0, 0), (1, 1, 1)))
    part.add(prism((2, 0, 0), (0.5, 0.5, 0.5)))
    model.write_step(tmp_path / "multi.step")
    text = (tmp_path / "multi.step").read_text(encoding="ascii")
    assert text.count("MANIFOLD_SOLID_BREP") == 2
    assert text.count("CLOSED_SHELL") == 2


def test_write_step_multiple_parts(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))
    model.part("pin").add(prism((0.1, 0.1, 0.01), (0.05, 0.05, 0.1)))
    model.write_step(tmp_path / "assembly.step")
    text = (tmp_path / "assembly.step").read_text(encoding="ascii")
    assert text.count("PRODUCT(") == 2
    assert text.count("MANIFOLD_SOLID_BREP") == 2


def test_write_step_rejects_sphere(tmp_path) -> None:
    model = Model("demo")
    model.part("ball").add(sphere((0, 0, 0), 1.0))
    with pytest.raises(WriteError, match="Sphere"):
        model.write_step(tmp_path / "ball.step")


def test_write_step_empty_model_raises(tmp_path) -> None:
    model = Model("demo")
    with pytest.raises(WriteError, match="no supported solids"):
        model.write_step(tmp_path / "empty.step")


def test_write_step_negative_size_prism(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((1, 1, 1), (-1, -0.5, -0.01)))
    model.write_step(tmp_path / "neg.step")
    text = (tmp_path / "neg.step").read_text(encoding="ascii")
    assert "MANIFOLD_SOLID_BREP" in text


def test_write_step_file_has_ap214_schema(tmp_path) -> None:
    model = Model("demo")
    model.part("box").add(prism((0, 0, 0), (1, 1, 1)))
    model.write_step(tmp_path / "box.step")
    text = (tmp_path / "box.step").read_text(encoding="ascii")
    assert "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));" in text
    assert "SI_UNIT($,.METRE.)" in text
