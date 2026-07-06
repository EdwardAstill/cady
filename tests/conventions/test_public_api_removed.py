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
    assert not hasattr(step, "read_step")
    assert not hasattr(step, "read_step_faces")
    assert not hasattr(stl, "write_ascii_stl")
    assert not hasattr(stl, "write_binary_stl")


def test_array_mesh_wrapper_is_not_public_api() -> None:
    assert not hasattr(operations, "ArrayMesh3")
    assert "ArrayMesh3" not in operations.__all__


def test_removed_vec_module_is_absent() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.vec") is None


def test_removed_operations_arrays_module_is_absent() -> None:
    import importlib.util

    assert importlib.util.find_spec("cady.operations.arrays") is None


def test_old_flat_operations_modules_are_absent() -> None:
    import importlib.util

    removed = (
        "cady.operations.coordinates",
        "cady.operations.mesh_clipping",
        "cady.operations.mesh_construction",
        "cady.operations.mesh_primitives",
        "cady.operations.mesh_topology",
    )

    for module in removed:
        assert importlib.util.find_spec(module) is None


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


def test_constructor_wrappers_are_removed() -> None:
    removed = {
        "arc2",
        "arc3",
        "box",
        "circle2",
        "cylinder",
        "line2",
        "line3",
        "polyline2",
        "polyline3",
        "region_circle",
        "region_rectangle",
        "sphere",
        "spline3",
    }

    for name in removed:
        assert not hasattr(cady, name), name
        assert name not in cady.__all__
        assert not hasattr(operations, name), name
        assert name not in operations.__all__


def test_drawing_convenience_wrappers_are_removed() -> None:
    from cady.drawing import BlockDefinition, Drawing2

    for name in (
        "add_text",
        "aligned_dimension",
        "angular_dimension",
        "diameter_dimension",
        "hatch",
        "linear_dimension",
        "radius_dimension",
        "with_layer",
    ):
        assert not hasattr(Drawing2, name), name
    for name in ("add", "add_text", "hatch"):
        assert not hasattr(BlockDefinition, name), name


def test_view_convenience_wrappers_are_removed() -> None:
    import cady.view as view

    assert not hasattr(view.Scene, "from_part")
    assert not hasattr(view.Scene, "from_assembly")
    assert not hasattr(view, "view_mesh")
    assert not hasattr(view, "view_meshes")


def test_mesh_stub_and_alias_methods_are_removed() -> None:
    from cady.geometry import Mesh3

    assert not hasattr(Mesh3, "triangulated")
    assert not hasattr(Mesh3, "close_holes")
