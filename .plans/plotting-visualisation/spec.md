# Plotting and Visualisation Split Plan

## Problem

The current `cady.visualisation` package mixes two related but different
jobs:

- plotting geometry into static or script-owned figures;
- opening an interactive viewer window where a user can inspect, orbit, pan,
  and zoom around an object.

That makes the API vocabulary fuzzy. A plot is an output artifact or figure.
A visualisation window is an interactive inspection surface. Users should be
able to choose either one directly.

## Decision

Split the public API into two optional leaf packages:

```text
cady.plotting       -> plots and figure-style outputs
cady.visualisation  -> native interactive inspection windows
```

`cady.plotting` owns plot functions. It can support 2D plots and 3D plots,
including Matplotlib today and potentially VisPy-backed plotting later.

`cady.visualisation` owns interactive object viewing. Its job is to bring up a
window where users can see the item natively, rotate/orbit it, pan, and zoom.
VisPy is the preferred direction for this layer because Cady already has
numeric mesh and polyline arrays that map naturally to GPU-backed visuals.

Keep both packages optional and import-light. Core object construction, file
export, and numeric operations must not require Matplotlib, VisPy, or any
viewer backend.

## Target API

### Plotting

Static/script-owned plotting should move to `cady.plotting`:

```python
from cady.plotting import plot_shape2d, plot_array_mesh3

fig, ax = plot_shape2d(profile, tolerance=1e-3, save_path="profile.png")
fig, ax = plot_array_mesh3(mesh, save_path="mesh.png", show=False)
```

Plotting functions should return caller-customisable figure/axis or plot
objects where the backend supports that.

Initial plotting API:

- `plot_shape2d(...)`
- `plot_drawing2d(...)`
- `plot_array_polyline2(...)`
- `plot_array_polygon2(...)`
- `plot_array_mesh3(...)`

The existing Matplotlib implementations can move here first. Later, plotting
may gain a VisPy backend for fast 3D plots, but that should still be considered
plotting when it is figure/output oriented rather than an object-inspection
viewer.

### Visualisation

Interactive inspection should live in `cady.visualisation`:

```python
from cady.visualisation import view_shape3d, view_model, visualise

view_shape3d(solid, tolerance=1e-3)
view_model(model)
visualise(part)
```

This layer should open a native interactive window by default. The user should
be able to rotate/orbit, pan, and zoom without manually wiring backend code.

Initial visualisation API:

- `view_shape2d(...)` for interactive 2D shape inspection if useful;
- `view_drawing2d(...)` for interactive drawing inspection if useful;
- `view_shape3d(...)`;
- `view_part(...)`;
- `view_model(...)`;
- `visualise(value, ...)` as a convenience dispatcher.

The first 3D backend should be VisPy unless implementation work proves a
different viewer backend is materially simpler. The viewer should consume
`to_array(...)` output rather than inspecting domain object internals.

## Object Methods

Native object methods are desirable, but they should remain thin convenience
wrappers:

```python
solid.visualise()
part.visualise()
model.visualise()
profile.plot()
```

If added, they must use lazy imports and preserve the boundary that domain and
numeric modules do not import plotting or visualisation at module scope.

Avoid embedding backend-specific rendering code in domain objects. The objects
should only delegate to the optional leaf packages.

## Module Boundaries

Target dependency direction:

```text
plotting -> domain/numeric
visualisation -> domain/numeric
domain/numeric/ops/files/exporters/importers -> no plotting or visualisation imports
```

`cady.plotting` and `cady.visualisation` are leaves. They can import semantic
and numeric geometry. Everything below them should stay usable without viewer
dependencies installed.

## Compatibility

Migrate additively first:

- add `cady.plotting` with the existing plot functions;
- keep temporary compatibility imports from `cady.visualisation` for existing
  plot functions;
- update docs and examples to prefer `cady.plotting` for plots;
- keep `cady.visualisation` focused on viewer functions;
- remove or deprecate compatibility exports later after public examples have
  moved.

## Done Criteria

- `cady.plotting` exists and owns all plot-oriented functions.
- `cady.visualisation` exposes interactive viewer functions only.
- Existing plot tests pass through `cady.plotting`.
- Compatibility tests cover old imports until deprecation/removal.
- Boundary tests ensure core packages do not import plotting or visualisation.
- README and visualisation docs explain the split clearly.
- A VisPy-backed interactive 3D viewer can show at least one mesh from
  `Shape3D`, `Part`, and `Model` with orbit/pan/zoom controls.
