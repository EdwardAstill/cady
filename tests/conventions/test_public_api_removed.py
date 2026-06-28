import cady
from cady.files import dxf, step, stl


def test_removed_top_level_api_names_are_not_exported() -> None:
    removed = {
        "DxfDrawing",
        "Extrusion",
        "Model",
        "Prism",
        "Rectangle",
        "Revolution",
        "SceneError",
        "Shape2",
        "Shape3",
        "Sphere",
        "StlMesh",
    }

    for name in removed:
        assert not hasattr(cady, name), name
        assert name not in cady.__all__


def test_removed_file_facade_functions_are_absent() -> None:
    for module in (dxf, step, stl):
        assert not hasattr(module, "write_model")
