import pytest

from cady import DxfDrawing, SceneError, StlMesh, WriteError, circle, prism


def test_geom_valueerror() -> None:
    with pytest.raises(ValueError):
        circle((0, 0), -1)


def test_scene_error() -> None:
    with pytest.raises(SceneError):
        DxfDrawing().layer("X").add(prism((0, 0, 0), (1, 1, 1)))  # type: ignore[arg-type]


def test_writer_error() -> None:
    with pytest.raises(WriteError):
        StlMesh().write("/tmp/empty.stl")
