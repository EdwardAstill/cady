from __future__ import annotations

import pytest

from cady import Model, WriteError, prism
from cady.model.core import Part
from cady.write.step.document import render_step
from cady.write.step.ids import IdAllocator


def test_id_allocator_returns_sequential_ids() -> None:
    ids = IdAllocator()
    assert ids.add("FOO('bar')") == 1
    assert ids.add("BAZ()") == 2


def test_id_allocator_renders_data_section() -> None:
    ids = IdAllocator()
    ids.add("FOO('x')")
    ids.add("BAR(#1)")
    assert ids.render_data() == "#1=FOO('x');\n#2=BAR(#1);"


def test_render_step_contains_iso_header() -> None:
    parts = [Model("m").part("plate")]
    parts[0].add(prism((0, 0, 0), (1, 0.5, 0.01)))
    text = render_step(parts, "plate")
    assert text.startswith("ISO-10303-21;")
    assert text.strip().endswith("END-ISO-10303-21;")
    assert "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));" in text


def test_render_step_contains_manifold_solid_brep_for_prism() -> None:
    part = Part("box")
    part.add(prism((0, 0, 0), (1, 1, 1)))
    text = render_step([part], "box_model")
    assert "MANIFOLD_SOLID_BREP" in text
    assert "CLOSED_SHELL" in text
    assert text.count("ADVANCED_FACE") == 6
    assert text.count("EDGE_CURVE") == 12


def test_render_step_rejects_sphere_solid() -> None:
    from cady import sphere
    part = Part("bad")
    part.add(sphere((0, 0, 0), 1.0))
    with pytest.raises(WriteError, match="Sphere"):
        render_step([part], "bad")


def test_model_write_step_produces_file(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))
    model.write_step(tmp_path / "demo.step")
    text = (tmp_path / "demo.step").read_text(encoding="ascii")
    assert "MANIFOLD_SOLID_BREP" in text


def test_render_step_extrusion_with_inner_loop_emits_hole() -> None:
    from cady import Extrusion, circle, polyline

    outline = polyline(
        [(-1, -1), (1, -1), (1, 1), (-1, 1)], closed=True
    ).with_hole(circle((0, 0), 0.25))

    part = Part("plate")
    part.add(Extrusion(profile=outline, axis="+z", distance=0.1))
    text = render_step([part], "plate")

    # 2 caps + 4 outer side faces + 32 inner side faces (circle segments)
    assert text.count("ADVANCED_FACE") == 2 + 4 + 32
    # Top + bottom caps each gain a FACE_BOUND for the hole
    assert text.count("FACE_BOUND") == 2
    assert text.count("FACE_OUTER_BOUND") == 2 + 4 + 32
    assert "MANIFOLD_SOLID_BREP" in text


def test_render_step_extrusion_rejects_non_polyline_inner_loop() -> None:
    from dataclasses import replace

    from cady import Extrusion, Vec2, polyline
    from cady.geom.shapes2d import Spline

    spline = Spline(
        control_points=(
            Vec2(-0.2, -0.2),
            Vec2(0.2, -0.2),
            Vec2(0.2, 0.2),
            Vec2(-0.2, 0.2),
        ),
        closed=True,
    )
    outer = polyline([(-1, -1), (1, -1), (1, 1), (-1, 1)], closed=True)
    outline = replace(outer, inner_loops=(spline,))

    part = Part("plate")
    part.add(Extrusion(profile=outline, axis="+z", distance=0.1))
    with pytest.raises(WriteError, match="inner loops only support"):
        render_step([part], "plate")
