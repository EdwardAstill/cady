import cady
import cady.operations as operations
import cady.operations.arrays as arrays
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


def test_array_mesh_wrapper_is_not_public_api() -> None:
    assert not hasattr(arrays, "ArrayMesh3")
    assert not hasattr(operations, "ArrayMesh3")
    assert "ArrayMesh3" not in operations.__all__
