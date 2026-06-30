import cady
import cady.measurement as measurement
import cady.operations as operations
import cady.product as product
from cady.files import dxf, step, stl


def test_removed_top_level_api_names_are_not_exported() -> None:
    removed = {
        "ClosedCurve2",
        "ClosedPolyline3",
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
        "Vec2",
        "Vec3",
    }

    for name in removed:
        assert not hasattr(cady, name), name
        assert name not in cady.__all__


def test_removed_file_facade_functions_are_absent() -> None:
    for module in (dxf, step, stl):
        assert not hasattr(module, "write_model")


def test_array_mesh_wrapper_is_not_public_api() -> None:
    assert not hasattr(operations, "ArrayMesh3")
    assert "ArrayMesh3" not in operations.__all__


def test_removed_vec_module_is_absent() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.vec") is None


def test_removed_operations_arrays_module_is_absent() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.operations.arrays") is None


def test_measurement_queries_are_not_operations_modules() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.operations.distances") is None
    assert importlib.util.find_spec("cady.operations.intersections") is None
    assert not hasattr(operations, "distance")
    assert not hasattr(operations, "intersect")


def test_length_is_not_a_measurement_function() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.measurement.length") is None
    assert not hasattr(measurement, "length")
    assert not hasattr(measurement, "intersect")


def test_product_convenience_wrappers_are_removed() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.product.flatten") is None
    assert not hasattr(product, "flatten_assembly")
    assert "flatten_assembly" not in product.__all__
    assert not hasattr(product.Part, "add_body")
    assert not hasattr(product.Assembly, "add")
