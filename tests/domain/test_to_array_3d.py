from __future__ import annotations

from cady import rectangle, sphere
from cady.numeric import ArrayMesh3


def test_prism_and_extrusion_convert_to_array_mesh() -> None:
    from cady import prism

    box = prism((0, 0, 0), (1, 1, 1)).to_array()
    assert isinstance(box, ArrayMesh3)
    assert box.faces.shape == (12, 3)

    plate = rectangle((0, 0), (1, 1)).extrude("+z", 0.1).to_array(tolerance=1e-2)
    assert isinstance(plate, ArrayMesh3)
    assert len(plate.faces) > 0


def test_sphere_converts_to_array_mesh() -> None:
    mesh = sphere((0, 0, 0), 0.5).to_array(tolerance=5e-2)
    assert isinstance(mesh, ArrayMesh3)
    assert mesh.triangles.shape[1:] == (3, 3)
