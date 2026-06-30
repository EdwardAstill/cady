from __future__ import annotations

from cady.operations import (
    AdvancingFrontMeshData,
    AdvancingFrontResult,
    advancing_front_surface,
)


def test_advancing_front_returns_primitive_mesh_data() -> None:
    points = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )

    mesh = advancing_front_surface(points, tolerance=1e-9)

    assert isinstance(mesh, AdvancingFrontMeshData)
    assert mesh.vertices == points
    assert mesh.faces == ((0, 1, 2),)
    assert mesh.edges == ((0, 1), (0, 2), (1, 2))


def test_advancing_front_stats_wrap_primitive_mesh_data() -> None:
    points = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )

    result = advancing_front_surface(points, tolerance=1e-9, return_stats=True)

    assert isinstance(result, AdvancingFrontResult)
    assert isinstance(result.mesh, AdvancingFrontMeshData)
    assert result.stats.vertices == 3
    assert result.stats.faces == 1
