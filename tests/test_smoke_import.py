import importlib

import pytest


def test_smoke_import() -> None:
    import cady

    expected = (
        "Arc2",
        "Arc3",
        "Assembly",
        "Body3",
        "Camera",
        "Circle2",
        "Curve2",
        "Curve3",
        "DirectionalLight",
        "DisplayStyle",
        "Document",
        "Drawing2",
        "Ellipse2",
        "Region3",
        "ScaleBarOverlay",
        "Plane3",
        "Layer",
        "Light",
        "Line2",
        "Line3",
        "LocalAxesOverlay",
        "Mesh3",
        "Mesh2",
        "Part",
        "PointLight",
        "PointCloud2",
        "PointCloud3",
        "Polyline3",
        "Region2",
        "Scene",
        "SceneOverlay",
        "Spline2",
        "Spline3",
        "Surface2",
        "Surface3",
        "Wireframe3",
        "arc3",
        "line3",
        "line2",
        "polyline3",
        "region_rectangle",
        "spline3",
        "box",
        "sphere",
    )

    assert cady is not None
    for name in expected:
        assert hasattr(cady, name), name

    removed = (
        "ClosedCurve2",
        "ClosedPolyline3",
        "ClosedPolyline2",
        "Face3",
        "Frame3",
        "Profile2",
        "profile_circle",
        "profile_rectangle",
    )
    for name in removed:
        assert not hasattr(cady, name), name


def test_preferred_package_imports() -> None:
    from cady import files
    from cady.drawing import Drawing2
    from cady.files import dxf, step, stl
    from cady.geometry import Body3, Line2, Mesh3, Region2, Surface2, Surface3
    from cady.measurement import distance, intersection
    from cady.operations import box, cut_mesh_by_plane, region_rectangle
    from cady.product import Assembly, Part
    from cady.vessels import Linesplan
    from cady.view import Camera, LocalAxesOverlay, RenderScene, ScaleBarOverlay, Scene

    assert all((Drawing2, Line2, Region2, Surface2, Surface3, Body3, Mesh3, Part, Assembly))
    assert all((Camera, Scene, ScaleBarOverlay, LocalAxesOverlay, RenderScene))
    assert all((region_rectangle, box, files))
    assert all((distance, intersection))
    assert Linesplan
    assert cut_mesh_by_plane
    assert all((dxf.render, dxf.write, dxf.read_drawing, dxf.read_mesh, dxf.read_wireframe))
    assert all((stl.write, step.render, step.write, step.read_faces))


def test_view_overlay_module_exports() -> None:
    from cady.view.overlay import LocalAxesOverlay, ScaleBarOverlay, SceneOverlay

    assert all((LocalAxesOverlay, ScaleBarOverlay, SceneOverlay))


def test_prepared_scene_name_is_removed_from_view_api() -> None:
    import cady.view

    assert hasattr(cady.view, "RenderScene")
    assert not hasattr(cady.view, "PreparedScene")


def test_removed_compatibility_package_replacements() -> None:
    from cady.geometry import Body3, Line2, Mesh3, Region2
    from cady.geometry import Body3 as NewBody3
    from cady.geometry import Line2 as NewLine2
    from cady.operations import box, cut_mesh_by_plane, region_rectangle
    from cady.operations import cut_mesh_by_plane as new_cut_mesh_by_plane

    assert Line2 is NewLine2
    assert Body3 is NewBody3
    assert all((Region2, Mesh3, region_rectangle, box))
    assert cut_mesh_by_plane is new_cut_mesh_by_plane


@pytest.mark.parametrize(
    "module",
    [
        "build",
        "domain",
        "geometry2",
        "geometry3",
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
        "linesplan",
    ],
)
def test_old_subpackages_are_removed(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"cady.{module}")
