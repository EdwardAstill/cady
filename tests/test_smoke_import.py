import importlib

import pytest


def test_smoke_import() -> None:
    import cady
    from cady import DxfDrawing, StlMesh, arc, circle, line, prism, sphere

    assert cady is not None
    assert all((line, arc, circle, sphere, prism, DxfDrawing, StlMesh))


def test_preferred_package_imports() -> None:
    from cady.build import rectangle
    from cady.domain import DxfDrawing, Model, Prism, Rectangle, StlMesh
    from cady.files import dxf, step, stl
    from cady.files.step import read_step_faces, render_step
    from cady.ops import midpoint

    assert all((Model, Rectangle, Prism, DxfDrawing, StlMesh))
    assert all((rectangle, midpoint, render_step, read_step_faces))
    assert all((dxf.read_drawing, dxf.write_drawing, step.read_faces, stl.write_model))


@pytest.mark.parametrize(
    "module",
    ["geom", "model", "scene", "write", "read", "exporters", "importers"],
)
def test_old_subpackages_are_removed(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"cady.{module}")
