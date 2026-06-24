from __future__ import annotations

import numpy as np

from cady.numeric.mesh3d import ArrayMesh3
from cady.product import Assembly, Part, flatten_assembly


def test_flatten_assembly_function_delegates_to_assembly_flatten() -> None:
    mesh = ArrayMesh3(np.array([[0.0, 0.0, 0.0]]), np.empty((0, 3), dtype=np.int64))
    part = Part("plate").with_body(mesh)
    assembly = Assembly("assy").add(part, name="plate_a")

    flattened = flatten_assembly(assembly)

    assert len(flattened) == 1
    assert flattened[0].part is part
    assert flattened[0].name == "plate_a"
