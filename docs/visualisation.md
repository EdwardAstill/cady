# Visualisation

`cady.visualisation` is the optional plotting and viewing layer. It depends on
domain and numeric geometry, while the core `cady` import stays independent of
viewer libraries.

Install `matplotlib` for 2D plotting and static 3D previews.

## 2D Plotting

Use `plot_shape2d(...)` for one shape and `plot_drawing2d(...)` for a drawing.
Both functions should default to equal axes, accept an optional Matplotlib
axis, and return the figure/axis for caller customisation.

```python
from cady import circle, rectangle
from cady.visualisation import plot_shape2d

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

fig, ax = plot_shape2d(
    profile,
    tolerance=1e-3,
    save_path="plate-profile.png",
    show=False,
)
```

Planned 2D helpers:

- `plot_shape2d(shape, *, tolerance=1e-3, ax=None, show=False, save_path=None)`
- `plot_drawing2d(drawing, *, tolerance=1e-3, ax=None, show=False, save_path=None)`
- `plot_array_polyline2(polyline, *, ax=None)`
- `plot_array_polygon2(polygon, *, ax=None)`

Filled profiles with holes should render as filled outer loops with cut-out
inner loops. Splines and arcs are sampled at the visualisation boundary using
the provided tolerance.

## 3D Viewing

Use `view_shape3d(...)` or `view_model(...)` for semantic objects, and
`plot_array_mesh3(...)` when a mesh has already been evaluated.

```python
from cady import circle, rectangle
from cady.visualisation import view_shape3d

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
solid = profile.extrude("+z", 0.04)

view_shape3d(
    solid,
    tolerance=1e-3,
    backend="matplotlib",
    show=True,
)
```

Planned 3D helpers:

- `plot_array_mesh3(mesh, *, ax=None, show=False, save_path=None)`
- `view_shape3d(shape, *, tolerance=1e-3, backend="matplotlib", show=True)`
- `view_model(model, *, tolerance=1e-3, backend="matplotlib", show=True)`

The baseline Matplotlib backend should work without an interactive display
when saving images.

## Saving Output

Use `save_path` for static images:

```python
plot_shape2d(profile, save_path="profile.png", show=False)
plot_array_mesh3(mesh, save_path="mesh.png", show=False)
```

Screenshot support for interactive backends depends on the backend. When a
backend cannot save a screenshot, the function should raise a clear error
rather than silently doing nothing.

## Example Script

From the repository root:

```bash
PYTHONPATH=src python examples/scripts/visualise_plate.py --out /tmp/cady-visualisation
```

The script builds the same plate as the model example and writes visualisation
images when the visualisation layer and optional backends are available.

## Layering Rules

Visualisation is a leaf package:

```text
visualisation -> domain
visualisation -> numeric
```

`domain`, `numeric`, `ops`, `files`, and the top-level `cady` package
should not import `visualisation`. This keeps normal model construction and
file export usable without plotting dependencies.
