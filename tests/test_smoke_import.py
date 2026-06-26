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
        "ClosedPolyline3D",
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
        "Mesh2D",
        "Part",
        "PointLight",
        "PointCloud3D",
        "Polyline3D",
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
    from cady.geometry import Body3D, Line2D, Mesh3D, Profile2D
    from cady.operations import box, cut_mesh_by_plane, profile_rectangle
    from cady.product import Assembly, Part
    from cady.view import Camera, Scene

    assert all((Drawing2D, Line2D, Profile2D, Body3D, Mesh3D, Part, Assembly))
    assert all((Camera, Scene, profile_rectangle, box, files))
    assert cut_mesh_by_plane
    assert all((dxf.render, dxf.write, dxf.read_drawing, dxf.read_mesh, dxf.read_wireframe))
    assert all((stl.write, step.render, step.write, step.read_faces))


def test_removed_compatibility_package_replacements() -> None:
    from cady.geometry import Body3D, Line2D, Mesh3D, Profile2D
    from cady.geometry import Body3D as NewBody3D
    from cady.geometry import Line2D as NewLine2D
    from cady.operations import box, cut_mesh_by_plane, profile_rectangle
    from cady.operations import cut_mesh_by_plane as new_cut_mesh_by_plane

    assert Line2D is NewLine2D
    assert Body3D is NewBody3D
    assert all((Profile2D, Mesh3D, profile_rectangle, box))
    assert cut_mesh_by_plane is new_cut_mesh_by_plane


@pytest.mark.parametrize(
    "module",
    [
        "build",
        "domain",
        "geometry2d",
        "geometry3d",
        "factories",
        "geom",
        "model",
        "ops",
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
