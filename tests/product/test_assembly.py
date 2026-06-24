from __future__ import annotations

import numpy as np
import pytest

from cady.numeric.mesh3d import ArrayMesh3
from cady.numeric.transform import Transform3
from cady.product import Assembly, Part, ProductError


def _point_mesh() -> ArrayMesh3:
    return ArrayMesh3(np.array([[0.0, 0.0, 0.0]]), np.empty((0, 3), dtype=np.int64))


def test_assembly_add_returns_new_assembly_and_reuses_parts_as_instances() -> None:
    part = Part("bolt").with_body(_point_mesh())
    original = Assembly("fixture")
    updated = (
        original.add(part, name="bolt_a", pose=(1.0, 0.0, 0.0))
        .add(part, name="bolt_b", pose=(2.0, 0.0, 0.0))
    )

    assert original.part_instances == ()
    assert [item.name for item in updated.part_instances] == ["bolt_a", "bolt_b"]

    mesh = updated.to_mesh(tolerance=1e-3)
    assert mesh.vertices.tolist() == [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]


def test_nested_assembly_flattening_applies_parent_before_child_pose() -> None:
    part = Part("pin").with_body(_point_mesh())
    child = Assembly("child").add(part, name="pin", pose=Transform3.translation(5.0, 0.0, 0.0))
    root = Assembly("root").add_assembly(
        child,
        name="child_a",
        pose=Transform3.translation(10.0, 0.0, 0.0),
    )

    flattened = root.flatten()
    assert len(flattened) == 1
    assert flattened[0].path == ("root", "child_a", "child", "pin")

    mesh = root.to_mesh(tolerance=1e-3)
    assert mesh.vertices.tolist() == [[15.0, 0.0, 0.0]]


def test_assembly_rejects_cycles_and_duplicate_instance_names() -> None:
    leaf = Assembly("leaf")
    branch = Assembly("branch").add_assembly(leaf)

    with pytest.raises(ProductError):
        leaf.add_assembly(branch)

    part = Part("plate").with_body(_point_mesh())
    with pytest.raises(ProductError):
        Assembly("assy").add(part, name="same").add(part, name="same")
