# Plotting and Visualisation File Plan

## New Files

### `src/cady/plotting/__init__.py`

Purpose: public namespace for plot-oriented functions.

Suggested exports:

```python
from cady.plotting.plot2d import (
    plot_array_polygon2,
    plot_array_polyline2,
    plot_drawing2d,
    plot_shape2d,
)
from cady.plotting.plot3d import plot_array_mesh3

__all__ = [
    "plot_array_mesh3",
    "plot_array_polygon2",
    "plot_array_polyline2",
    "plot_drawing2d",
    "plot_shape2d",
]
```

### `src/cady/plotting/plot2d.py`

Move current 2D Matplotlib plotting code here from:

- `src/cady/visualisation/plot2d.py`

Error messages should say "plotting" rather than "visualisation" where the
function is plot-oriented.

### `src/cady/plotting/plot3d.py`

Move static 3D plotting code here from:

- `src/cady/visualisation/view3d.py`

This file should own `plot_array_mesh3(...)`. It may keep Matplotlib as the
first backend and can later add VisPy-backed plot output if useful.

### `src/cady/visualisation/view3d.py`

Refocus on interactive window viewing.

Target responsibilities:

- collect meshes from `Shape3D`, `Part`, or `Model`;
- dispatch to an interactive backend;
- use VisPy as the intended native viewer backend;
- keep backend imports lazy.

### `src/cady/visualisation/vispy.py`

Optional implementation module for VisPy-specific code.

Suggested responsibilities:

- create a scene canvas;
- add mesh visuals from `ArrayMesh3` values;
- configure orbit/pan/zoom camera controls;
- show the window and return a useful viewer/canvas object.

## Existing Files To Touch

### `src/cady/visualisation/__init__.py`

After the split, export viewer functions first.

During compatibility, it can also re-export plotting functions from
`cady.plotting`.

### `src/cady/visualisation/plot2d.py`

Move or replace with a compatibility shim.

Preferred temporary shim:

```python
from cady.plotting.plot2d import (
    plot_array_polygon2,
    plot_array_polyline2,
    plot_drawing2d,
    plot_shape2d,
)
```

### `src/cady/visualisation/styles.py`

Either move to `src/cady/plotting/styles.py` or split style constants if
plotting and interactive viewer styling diverge.

### `tests/visualisation/*`

Move plot-specific tests to `tests/plotting/`.

Keep interactive viewer tests under `tests/visualisation/`.

### `tests/conventions/test_import_boundaries.py`

Extend boundary checks so core packages do not import either:

- `cady.plotting`
- `cady.visualisation`

### `tests/conventions/test_stdlib_only.py`

Update optional dependency allowlists:

- `plotting`: Matplotlib and `mpl_toolkits`;
- `visualisation`: VisPy and any viewer-only backend modules.

### `pyproject.toml`

Consider splitting extras:

- `plotting`
- `visualisation`
- possibly compatibility extra names during migration

### `README.md`

Update the architecture text and examples to distinguish plotting from
interactive visualisation.

### `docs/visualisation.md`

Either narrow this file to interactive viewing or split it:

- `docs/plotting.md`
- `docs/visualisation.md`

### `examples/scripts/visualise_plate.py`

Decide whether this remains an interactive visualisation example or becomes a
plotting example. If it writes PNGs, it should likely move toward
`plot_plate.py` or import from `cady.plotting`.

## Files To Avoid Touching Initially

Avoid changing domain object internals until the package split and tests are
stable:

- `src/cady/domain/base.py`
- `src/cady/domain/model.py`
- `src/cady/domain/shapes2d.py`
- `src/cady/domain/shapes3d.py`

Object-level `.plot()` and `.visualise()` methods can be added in a later
small pass once the optional packages have clear ownership.
