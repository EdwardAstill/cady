from __future__ import annotations


def test_visualisation_package_imports_without_optional_backend_use() -> None:
    import cady
    import cady.visualisation

    assert cady.visualisation.plot_shape2d
    assert cady.visualisation.view_shape3d
    assert cady.visualisation.view_part
    assert cady.visualisation.visualise
    assert cady
