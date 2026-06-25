import importlib

import pytest


def test_smoke_import() -> None:
    import cady

    expected = (
        "Arc2D",
        "Assembly",
        "Body3D",
        "Camera",
        "Circle2D",
        "ClosedPolyline2D",
        "Curve2D",
        "DirectionalLight",
        "DisplayStyle",
        "Document",
        "Drawing2D",
        "Ellipse2D",
        "Face3D",
        "Frame3D",
        "Layer",
        "Light",
        "Line2D",
        "Mesh3D",
        "Part",
        "PointLight",
        "Pose3D",
        "Profile2D",
        "Scene",
        "Spline2D",
        "Vec2",
        "Vec3",
        "Wireframe3D",
        "line2d",
        "profile_rectangle",
        "box",
        "sphere",
    )

    assert cady is not None
    for name in expected:
        assert hasattr(cady, name), name


def test_preferred_package_imports() -> None:
    from cady import files
    from cady.drawing import Drawing2D
    from cady.files import dxf, step, stl
    from cady.geometry2d import Line2D, Profile2D, profile_rectangle
    from cady.geometry3d import Body3D, Mesh3D, box
    from cady.product import Assembly, Part
    from cady.view import Camera, Scene

    assert all((Drawing2D, Line2D, Profile2D, Body3D, Mesh3D, Part, Assembly))
    assert all((Camera, Scene, profile_rectangle, box, files))
    assert all((dxf.render, dxf.write, dxf.read_drawing, dxf.read_mesh, dxf.read_wireframe))
    assert all((stl.write, step.render, step.write, step.read_faces))


@pytest.mark.parametrize(
    "module",
    [
        "build",
        "domain",
        "geom",
        "model",
        "scene",
        "write",
        "read",
        "exporters",
        "importers",
        "plotting",
    ],
)
def test_old_subpackages_are_removed(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"cady.{module}")
