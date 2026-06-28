# cady Agent Guide

cady is a small native CAD package for immutable geometry values, meshable
3D bodies, product assemblies, 2D drawings, view scenes, and DXF/STL/STEP file
facades. It is intentionally lightweight: no CAD kernel, no eager viewer imports,
and no runtime dependencies beyond the declared allowlist.

This repository is in the middle of a naming and layout cleanup. Treat the source
tree and tests as authoritative when docs disagree. Current public names are
suffixless (`Line2`, `Body3`, `Drawing2`, `Text2`, `Pose3`), not the older
`Line2D`/`Body3D`/`Drawing2D` style.

## Non-Negotiables

- Preserve immutable value semantics. Public geometry, drawing, product, view,
  vector, transform, and metadata objects should return new values rather than
  mutate existing instances.
- Keep authoring objects semantic until an explicit boundary: `to_array(...)`,
  `to_mesh(...)`, file write/render functions, or view preparation.
- Every sampling, meshing, and export path must take `tolerance` explicitly as a
  keyword argument. Do not hide new discretisation constants in implementation
  code.
- Keep module imports light. Optional GUI or plotting dependencies must be
  imported only inside functions that actually launch or prepare those paths.
- Do not reintroduce removed packages or aliases: `domain`, `build`, `numeric`,
  `factories`, `visualisation`, `geometry2`, `geometry3`, `ops`, or old public
  names such as `Model`, `Shape2`, `Shape3`, `Rectangle`, `Prism`, `Extrusion`,
  `Revolution`, `Sphere`, `DxfDrawing`, `StlMesh`, and `SceneError`.
- Prefer current local patterns over new abstractions. This codebase uses frozen
  dataclasses, tuple-backed immutable fields, local validation helpers, and late
  imports to maintain boundaries.

## Current Package Layout

```text
src/cady/
  geometry/      semantic 2D/3D values: curves, regions, surfaces, meshes, bodies
  operations/    NumPy-backed arrays, transforms, validation, sampling, meshing
  drawing/       Drawing2 documents, layers, text, hatches, inserts, dimensions
  product/       Part, Assembly, Material, flattening
  view/          backend-independent Scene API and optional Vispy viewer
  files/         flat DXF/STL/STEP facades
  document.py    optional project registry
  vec.py         Vec2 and Vec3
  errors.py      shared exception hierarchy
```

There is one geometry package, `cady.geometry`, and one numeric/algorithm package,
`cady.operations`. Do not add split packages like `geometry2`, `geometry3`,
`numeric`, or `ops`.

## Boundary Model

Authoring layer:

- `Vec2`, `Vec3`
- 2D geometry: `Line2`, `Arc2`, `Spline2`, `Polyline2`, `Circle2`, `Ellipse2`,
  `Region2`, `Mesh2`, `PointCloud2`
- 3D geometry: `Line3`, `Arc3`, `Spline3`, `Polyline3`, `ClosedPolyline3`,
  `Plane3`, `Surface2`, `Surface3`, `Region3`, `Mesh3`, `Wireframe3`,
  `PointCloud3`, `Body3`
- documents and products: `Drawing2`, `Part`, `Assembly`, `Document`, `Scene`

Evaluation layer:

- `ArrayBezierSpline2`, point arrays, and plain mesh array tuples
- `Transform2`, `Transform3`, `Pose3`
- validation helpers in `operations.validation`
- array/mesh algorithms in `operations.*`

Allowed flow:

```text
semantic value -> to_array(tolerance=...) -> array value
semantic value -> to_mesh(tolerance=...)  -> Mesh3
semantic value -> files.*.write/render(...) or view.prepare_scene(...)
```

Avoid the reverse dependency. `operations` should not import `drawing`,
`product`, `view`, or `files`; domain methods unpack their fields and pass
primitive data into operations helpers.

## Import Rules Enforced By Tests

The convention tests are part of the architecture:

- `tests/conventions/test_import_boundaries.py`
  - removed legacy packages must not exist
  - `geometry`, `drawing`, `product`, and `view` must not import `cady.domain`
  - `operations` must not import domain/application packages
  - `files` must not import `numpy` or viewer backend modules at module scope
  - export code must not hide discretisation constants
- `tests/conventions/test_stdlib_only.py`
  - runtime imports are limited to stdlib, `cady`, `numpy`, and `steputils`
  - optional extras are only allowed in their intended package paths
- `tests/conventions/test_public_api_removed.py`
  - old top-level names and `write_model(...)` must stay absent

Run these tests after edits that touch imports, facades, exports, package layout,
or public names.

## Public API Shape

Top-level `cady` re-exports currently include:

- constructors: `line2`, `arc2`, `line3`, `arc3`, `spline3`, `polyline2`,
  `polyline3`, `circle2`, `region_rectangle`, `region_circle`, `box`,
  `cylinder`, `sphere`
- geometry: `Line2`, `Line3`, `Arc2`, `Arc3`, `Spline2`, `Spline3`,
  `Polyline2`, `Polyline3`, `ClosedPolyline3`, `Circle2`, `Ellipse2`,
  `Region2`, `Region3`, `Surface2`, `Surface3`, `Plane3`, `Mesh2`, `Mesh3`,
  `Wireframe3`, `PointCloud2`, `PointCloud3`, `Body3`
- geometry protocols: `Curve2`, `ClosedCurve2`, `Curve3`
- drawing: `Drawing2`, `DrawingEntity`, `Layer`, `Text2`, `Hatch2`, `Insert2`,
  `BlockDefinition`, `DimStyle`, dimension classes
- product: `Part`, `PartInstance`, `Assembly`, `AssemblyInstance`, `Material`
- view: `Scene`, `SceneObject`, `Camera`, `Light`, `AmbientLight`,
  `DirectionalLight`, `PointLight`, `DisplayStyle`
- other: `Document`, `Vec2`, `Vec3`, `Pose3`, shared error classes

When adding a public value, update the local package `__init__.py`, then
`src/cady/__init__.py`, then tests. Do not add backwards-compatible aliases for
removed names unless the tests and project direction change first.

## Geometry Notes

- `Line2`, `Arc2`, `Circle2`, `Ellipse2`, `Spline2`, and `Polyline2` live in
  separate focused modules under `geometry/`.
- `Polyline2` can be open or closed. Only closed `Polyline2` values can produce
  `Mesh2`.
- `Region2` is a filled planar region with one closed outer loop and optional
  holes.
- `Plane3` is the placement frame for planar 3D work. It owns origin, x-axis,
  y-axis, and normal handling.
- `Surface3` supports parametric surfaces; `Region3` places a 2D parameter
  region on a `Surface3`.
- `Polyline3` can be built from points or from curve objects implementing the
  `Curve3` protocol. `ClosedPolyline3` validates planarity before meshing.
- `Mesh3` is the semantic triangle mesh type and carries optional display edges.
- `Wireframe3` is edge-only topology. It has helpers for edge splitting,
  triangulation, loft-style conversion, and close-to-plane workflows.
- `PointCloud2` and `PointCloud3` are unconnected point collections. They are
  not curves, meshes, or wireframes.
- `Body3` is a feature-history body. Currently meshable paths are region
  extrusion and box/cylinder/sphere primitives. Revolve, boolean, fillet, and
  chamfer features are records only until their evaluators are implemented.

## Operations Notes

Use `cady.operations` for array and primitive algorithms:

- `constructors.py` contains import-light factory wrappers used by the public
  API.
- `validation.py`, `bounds.py`, `types.py`, `arrays2.py`, and `arrays3.py` own
  NumPy-backed value validation and containers.
- `transforms.py` owns `Transform2`, `Transform3`, `Pose3`, and point-level
  transform functions.
- `sampling2.py`, `polygons2.py`, `triangulation.py`, and `profiles.py` own
  curve/region sampling and 2D polygon helpers.
- `_mesh_builders.py`, `_mesh_arrays.py`, `mesh_primitives.py`,
  `mesh_clipping.py`, `mesh_caps.py`, `mesh_boundaries.py`, `mesh_topology.py`,
  and `planes.py` own mesh construction and topology algorithms.
- `linesplan.py` and `section_loft.py` handle imported section/wire geometry
  workflows.

Operations code may import `numpy` and standard library modules. Keep it free of
application-level package imports so it remains reusable and testable.

## Files And I/O

File facades are flat modules:

- `cady.files.dxf`
  - reads basic 2D drawing entities, `3DFACE` meshes, and 3D polyline-style
    wire curves
  - writes `Drawing2` as ASCII DXF R2018
  - `read_mesh` no longer converts line geometry into mesh faces
- `cady.files.stl`
  - writes ASCII or binary STL from meshable targets
- `cady.files.step`
  - writes mesh-oriented STEP output from meshable targets
  - reads elementary STEP faces and extracts simple member data
- `cady.files.utils.mesh_from_target`
  - shared conversion boundary for `Mesh3`, `Body3`, `Part`, `Assembly`, and
    meshable `Document` contents

`files` modules should convert at the boundary and keep imports local when a
dependency would violate convention tests.

## View Layer

`cady.view` is backend-independent until viewer helpers are requested. Its
`__getattr__` lazily exposes Vispy helpers such as `view_scene`, `view_target`,
`view_mesh`, `view_meshes`, `view_lines`, and `prepare_scene`.

Do not import PyQt, Vispy, or OpenGL modules from core geometry/product/drawing
code. User-facing `.view(...)` methods should late-import `open_target_view`.

## Editing Recipes

### Add or change a geometry value

1. Edit the focused module under `src/cady/geometry/`.
2. Keep the dataclass frozen and store tuple-backed immutable fields.
3. Validate construction inputs immediately.
4. Add `bounds()`, `points()`, `to_array(tolerance=...)`, `to_mesh(tolerance=...)`,
   or transform/mirror helpers only where they make sense for that type.
5. Put numeric work in `operations`, not in large inline domain methods.
6. Update exports and focused tests.

### Add or change a meshable body feature

1. Add the feature record in `geometry/body3.py` only if it belongs to `Body3`
   history.
2. Add evaluation in `operations/_mesh_builders.py` or a focused mesh helper.
3. Wire `_feature_to_mesh` and transform behavior.
4. Add tests for successful meshing and unsupported paths.

### Add an operation

1. Place it in `src/cady/operations/`.
2. Accept arrays, tuples, scalars, and operation-local types.
3. Return arrays, tuples, operation-local containers, or semantic values only at
   existing conversion points.
4. Do not import authoring/application packages.

### Add or change file output

1. Keep public entry points in `src/cady/files/dxf.py`, `stl.py`, or `step.py`.
2. Require or preserve explicit `tolerance` on public render/write functions.
3. Add file-level regression tests under `tests/files/`.
4. Check import boundary tests after changing module-scope imports.

### Update docs or examples

Use current suffixless names. Do not add new examples using `Line2D`, `Body3D`,
`Drawing2D`, `line2d`, or similar old spelling unless the API itself changes.

## Tests

Run from the repository root:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

Use `PYTHONPATH=src` for scripts:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
```

Test areas:

- `tests/geometry/`: geometry values, regions, body meshing, point clouds,
  wireframes, linesplan behavior
- `tests/operations/`: validation, transforms, mesh clipping/capping, sampling,
  numeric mesh helpers
- `tests/drawing/`: drawings, layers, dimensions, entities
- `tests/product/`: parts, assemblies, flattening
- `tests/view/`: scene model and viewer smoke coverage
- `tests/files/`: DXF/STL/STEP facades
- `tests/examples/`: example script regressions
- `tests/conventions/`: import boundaries, runtime dependency allowlist,
  removed API checks

## Development Hygiene

- Expect a dirty worktree during active refactors. Do not revert unrelated user
  changes.
- Prefer `rg` and targeted file reads over broad manual inspection.
- Keep edits scoped. This project intentionally has small modules and explicit
  boundaries.
- If docs and code disagree, update docs toward source and tests rather than
  bending code back toward stale docs.
- Before finishing non-trivial code changes, run the narrow relevant tests plus
  convention tests. For public API or architecture changes, run the full gates.
