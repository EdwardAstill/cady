from __future__ import annotations


def test_plotting_package_imports_without_optional_backend_use() -> None:
    import cady.plotting

    assert cady.plotting.plot_shape2d
    assert cady.plotting.plot_array_mesh3


def test_visualisation_keeps_plotting_compatibility_imports() -> None:
    import cady.plotting
    import cady.visualisation

    assert cady.visualisation.plot_shape2d is cady.plotting.plot_shape2d
    assert cady.visualisation.plot_array_mesh3 is cady.plotting.plot_array_mesh3
