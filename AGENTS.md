# cady Agent Guide

cady is a small native CAD package for immutable geometry values, meshable
3D bodies, product assemblies, 2D drawings, view scenes, and DXF/STL/STEP file
facades. It is intentionally lightweight: no CAD kernel, no eager viewer imports,
and runtime imports are restricted by convention tests to stdlib, `cady`,
`numpy`, and `steputils`.

Treat the source tree and tests as authoritative when docs disagree. Current
public names are suffixless (`Line2`, `Body3`, `Drawing2`, `Text2`),
not the older `Line2D`/`Body3D`/`Drawing2D` style.

## Non-Negotiables

- Preserve immutable value semantics. Public geometry, drawing, product, view,
  transform, and metadata objects should return new values rather than mutate
  existing instances.
- Keep authoring objects semantic until an explicit boundary: `to_array(...)`,
  `to_mesh(...)`, file write/render functions, or view preparation.
- Sampling, meshing, and export APIs must expose `tolerance` as a keyword
  argument. Domain `to_array(...)` and `to_mesh(...)` methods should require it;
  facades that default it must still pass it through explicitly.
- Keep module imports light. Optional GUI dependencies must be imported only
  inside functions or lazily imported viewer modules that actually launch or
  prepare those paths.
- Do not add compatibility aliases, duplicate public entry points, or parallel
  operation/API paths. Each operation or API process should have one canonical
  way to do it; remove or migrate old paths instead of preserving shims.
- Do not reintroduce removed packages or aliases: `build`, `domain`,
  `exporters`, `factories`, `geom`, `geometry2`, `geometry3`, `importers`,
  `model`, `numeric`, `ops`, `plotting`, `read`, `scene`, `visualisation`, or
  `write`.
- Do not reintroduce old public names such as `ClosedCurve2`, `ClosedPolyline2`,
  `ClosedPolyline3`, `DxfDrawing`, `Extrusion`, `Face3`, `Frame3`, `Model`,
  `Prism`, `Profile2`, `Rectangle`, `Revolution`, `SceneError`, `Shape2`,
  `Shape3`, `Sphere`, `StlMesh`, `Vec2`, `Vec3`, `profile_circle`,
  `profile_rectangle`, or `write_model(...)`.
- Prefer current local patterns over new abstractions. This codebase uses frozen
  dataclasses, tuple-backed immutable fields, minimal local validation, operation
  modules for numeric work, and late imports to maintain boundaries.

## Maintainability Bias

- Prefer obvious code over clever abstractions. A little repetition is better
  than a helper that hides simple logic or makes call sites harder to read.
- Add helper functions only when they name a real domain concept, remove
  meaningful duplication, or isolate genuinely tricky logic.
- Keep validation at public construction points and explicit conversion/export
  boundaries. Avoid defensive validation inside every internal helper unless the
  invariant is genuinely hard to preserve.
- Keep modules readable top-to-bottom. Avoid splitting small, related logic
  across many files just to make the structure look more abstract.
- When changing code, preserve the local style first. Do not introduce a new
  pattern unless it clearly improves the current module and is worth applying
  consistently.
- Tests should pin behavior, not implementation structure. Avoid tests that make
  simple refactors painful unless the structure is itself part of the contract.

## Current Package Layout

```text
src/cady/
  geometry/      semantic 2D/3D values: curves, regions, surfaces, meshes, bodies
  operations/    NumPy-backed transforms, triangulation, meshing
  measurement/   two-geometry distance/intersection and future area/volume queries
  drawing/       Drawing2 documents, layers, text, hatches, inserts, dimensions
  product/       Part, Assembly, Material, flattening
  view/          backend-independent Scene API and optional Vispy viewer helpers
  files/         flat DXF/STL/STEP facades
  vessels/       vessel-specific helpers such as Linesplan station meshing
  document.py    immutable registry for drawings, parts, assemblies, and scenes
  errors.py      shared exception hierarchy
  utils.py       small validation and topology helpers
```

There is one geometry package, `cady.geometry`, and one numeric/algorithm
package, `cady.operations`. Do not add split packages like `geometry2`,
`geometry3`, `numeric`, or `ops`.

## Boundary Model

Authoring layer:

- Points are plain tuples (`tuple[float, float]` and
  `tuple[float, float, float]`) validated at construction or conversion
  boundaries. There are no public `Vec2` or `Vec3` classes.
- 2D geometry: `Line2`, `Arc2`, `Spline2`, `Polyline2`, `Circle2`, `Ellipse2`,
  `Region2`, `Mesh2`, `PointCloud2`
- 3D geometry: `Line3`, `Arc3`, `Spline3`, `Polyline3`, `Plane3`, `Surface2`,
  `Surface3`, `Region3`, `Mesh3`, `Wireframe3`, `PointCloud3`, `Body3`
- documents, products, and domain helpers: `Drawing2`, `Part`, `Assembly`,
  `Document`, `Scene`, `Linesplan`

Evaluation layer:

- Array and primitive helpers should live in the operation module that uses
  them. For type-checking clarity and safety, define small type aliases near the
  top of that file when they make the code easier to read.
- `operations.transforms` owns `Transform2` and `Transform3`.
- `operations.primitives`, `transforms`, `operations.mesh.construction`,
  `operations.mesh.primitives`, `operations.mesh.clipping`,
  `operations.mesh.topology`, `triangulation`, `surface_reconstruction`,
  `lofting`, and `wireframes` own numeric algorithms.
- `measurement` owns object-level distance, intersection, area, and volume-style
  queries. It may import `geometry` objects.
- `vessels` owns higher-level domain workflows such as DXF linesplan cleanup,
  station sampling, and conversion to `Wireframe3` or `Mesh3`.

Allowed flow:

```text
semantic value -> to_array(tolerance=...) -> array value
semantic value -> to_mesh(tolerance=...)  -> Mesh2 or Mesh3
semantic value -> files.*.write/render(...) or view.prepare_scene(...)
```

Avoid the reverse dependency. `operations` must not import `drawing`, `product`,
`view`, or `files`; semantic methods unpack their fields and pass primitive data
into operations helpers.

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
  - optional GUI imports are loaded through lazy viewer code rather than module
    scope imports in the public API
- `tests/conventions/test_public_api_removed.py`
  - old top-level names and `write_model(...)` must stay absent
  - `ArrayMesh3` must not become public API
- `tests/test_smoke_import.py`
  - preferred packages and current top-level re-exports must import cleanly
  - old compatibility subpackages must continue to be absent

Run these tests after edits that touch imports, facades, exports, package layout,
or public names.

## Public API Shape

Top-level `cady` re-exports currently include:

- constructors: `line2`, `arc2`, `line3`, `arc3`, `spline3`, `polyline2`,
  `polyline3`, `circle2`, `region_rectangle`, `region_circle`, `box`,
  `cylinder`, `sphere`
- geometry: `Line2`, `Line3`, `Arc2`, `Arc3`, `Spline2`, `Spline3`,
  `Polyline2`, `Polyline3`, `Circle2`, `Ellipse2`, `Region2`, `Region3`,
  `Surface2`, `Surface3`, `Plane3`, `Mesh2`, `Mesh3`, `Wireframe3`,
  `PointCloud2`, `PointCloud3`, `Body3`
- geometry protocols: `Curve2`, `Curve3`
- drawing: `Drawing2`, `DrawingEntity`, `Layer`, `Text2`, `Hatch2`, `Insert2`,
  `BlockDefinition`, `DimStyle`, `LinearDimension2`, `AlignedDimension2`,
  `RadiusDimension2`, `DiameterDimension2`, `AngularDimension2`
- product: `Part`, `PartInstance`, `Assembly`, `AssemblyInstance`, `Material`
- view: `Scene`, `SceneObject`, `Camera`, `Light`, `AmbientLight`,
  `DirectionalLight`, `PointLight`, `DisplayStyle`, `ScaleBarOverlay`,
  `LocalAxesOverlay`, `SceneOverlay`
- other: `Document` and shared error classes

Subpackage exports are broader than top-level exports:

- `cady.operations` also exports `Transform2`, `Transform3`, mesh clipping
  helpers, triangulation helpers, and `sphere_triangles`.
- `cady.measurement` exports object-level query helpers such as `distance(...)`
  and `intersection(...)`, plus their small result dataclasses.
- `cady.drawing` also exports `DrawingItem`, `Dimension2`, and
  `format_measurement`.
- `cady.product` also exports `FlattenedPart` and `ProductError`.
- `cady.vessels` exports `Linesplan`; it is intentionally not re-exported from
  top-level `cady`.
- `cady.view` exposes backend-independent preparation types and helpers:
  `RenderScene`, `SceneLine`, `SceneMesh`, and `prepare_scene`. It lazily
  exposes viewer-opening helpers: `view_scene` and `view_lines`.
- `cady.document` also exports `DocumentItem`, `DocumentKind`, and
  `document_from_mapping`.

When adding a public value, update the local package `__init__.py`, then
`src/cady/__init__.py` if it belongs at top level, then tests. Do not add
backwards-compatible aliases for removed names or secondary spellings for new
names.

## Geometry Notes

- `Line2`/`Line3`, `Arc2`/`Arc3`, `Circle2`/`Ellipse2`, `Spline2`/`Spline3`,
  `Polyline2`/`Polyline3`, regions, surfaces, meshes, point clouds, wireframes,
  planes, and bodies live in focused modules under `geometry/`.
- `Polyline2` can be open or closed. Only closed `Polyline2` values can produce
  `Mesh2`.
- `Polyline3` can be built from points or from curve objects implementing the
  `Curve3` protocol. It has a `closed` flag; there is no separate
  `ClosedPolyline3` class. Closed `Polyline3.to_mesh(...)` validates planarity
  before triangulating.
- `Region2` is a filled planar region with one closed outer loop and optional
  holes.
- `Plane3` is the placement frame for planar 3D work. It owns origin, x-axis,
  y-axis, and normal handling.
- `Surface3` supports parametric surfaces; `Region3` places a 2D parameter
  region on a `Surface3`.
- `Mesh3` is the semantic triangle mesh type and carries optional display edges.
  `Mesh2` is the 2D triangle mesh type.
- `Wireframe3` is edge-only topology. It has helpers for edge splitting,
  triangulation, loft-style conversion, and close-to-plane workflows.
- `PointCloud2` and `PointCloud3` are unconnected point collections. They are
  not curves, meshes, or wireframes.
- `Body3` is a feature-history body. Currently meshable paths are region
  extrusion and box/cylinder/sphere primitives. Cone, revolve, boolean, fillet,
  and chamfer features are records only until their evaluators are implemented.

## Operations Notes

Use `cady.operations` for array and primitive algorithms:

- Keep one canonical operation path for each workflow. Do not keep compatibility
  re-export modules, old helper names, or alternate APIs once a clearer module
  or function name exists.
- Do not recreate a central `operations/arrays.py` module. Keep NumPy-backed
  helper logic close to the operation that needs it, and use file-local type
  aliases at the top of the file when that improves type checking and safety.
- Keep validation minimal. Validate public construction inputs and explicit
  conversion boundaries, but avoid broad helper layers that make the code harder
  to read or complicate straightforward geometry logic.
- `primitives.py` contains low-level tuple/vector math.
- `mesh/construction.py` owns conversion-oriented meshing helpers for closed
  polylines, surface regions, region extrusions, and wireframe-to-mesh
  workflows.
- `mesh/primitives.py` contains primitive triangle builders and semantic
  `Mesh3` constructors for simple primitive bodies.
- `linesplan_meshing.py` owns linesplan curve classification and simple station
  network meshing.
- `mesh/clipping.py` owns plane cuts and planar/boundary closure helpers.
- `mesh/topology.py` owns mesh simplification and topology operations such as
  decimation.
- `transforms.py` contains `Transform2` and `Transform3`.
- `triangulation.py` contains polygon triangulation and deduplication helpers.
- `surface_reconstruction/` owns point-cloud-to-surface reconstruction
  algorithms such as advancing front.
- `lofting.py` and `wireframes.py` own focused lofting and wireframe
  algorithms.

Operations code may import `numpy` and standard library modules. Keep it free of
application-level package imports so it remains reusable and testable.

Use `cady.measurement` for object-level geometric queries:

- `distance.py` contains distances and closest-point result records.
- `intersection.py` contains `intersection(...)` dispatch and result records.
- exact curve length belongs on geometry values as `.length`, not in a
  measurement module.
- `volume.py` is reserved for future meshable volume measurement.

## Vessel Helpers

`cady.vessels` contains domain-specific helpers that sit above geometry,
operations, and file facades. Keep vessel workflows semantic at the public API
and push numeric work into operations modules when it becomes reusable.

- `Linesplan.from_dxf(...)` reads station curves through the DXF facade, cleans
  and mirrors station polylines, and stores the configured sample count as
  `nodes_on_polyline`.
- `Linesplan.to_grid_wireframe(...)` samples stations into a `Wireframe3`.
- `Linesplan.to_mesh(...)` builds a closed triangular `Mesh3` from the sampled
  station grid and caps.

## Files And I/O

File facades are flat modules:

- `cady.files.dxf`
  - `read(...)` returns a `DxfImportResult` with `drawing`, `meshes`, `curves`,
    `wireframes`, and `skipped` data
  - reads basic 2D drawing entities, `3DFACE` meshes, and 3D polyline-style
    wire curves
  - writes `Drawing2` as ASCII DXF R2018
  - `read_mesh(...)` no longer converts line geometry into mesh faces and
    rejects legacy line-mesh keyword arguments
  - `read_curves(...)` returns `DxfWireCurve` records and `read_wireframe(...)`
    merges imported wireframes
- `cady.files.stl`
  - writes ASCII or binary STL from meshable targets
- `cady.files.step`
  - writes mesh-oriented STEP output from meshable targets
  - reads elementary STEP faces and extracts simple extruded member data
- `cady.files.utils.mesh_from_target`
  - shared conversion boundary for `Mesh3`, `Body3`, `Part`, `Assembly`, and
    meshable `Document` contents

`files` modules should convert at the boundary and keep imports local when a
dependency would violate convention tests.

## View Layer

`cady.view` is backend-independent until viewer-opening helpers are requested.
Its `__getattr__` lazily exposes Vispy-facing helpers such as `view_scene` and
`view_lines`. The backend-independent `RenderScene`, `SceneLine`, `SceneMesh`,
and `prepare_scene` values live in `scene.py`.

Do not import PyQt, Vispy, or OpenGL modules from core geometry/product/drawing
code. User-facing `.view(...)` methods should late-import
`cady.view.viewer.open_target_view`.

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
2. Add evaluation in `operations/mesh/primitives.py` or a focused operations
   helper.
3. Wire `_feature_to_mesh` and transform behavior.
4. Add tests for successful meshing and unsupported paths.

### Add an operation

1. Place it in a focused module under `src/cady/operations/`.
2. Accept arrays, tuples, scalars, and operation-local types.
3. Return arrays, tuples, operation-local containers, or semantic values only at
   existing conversion points.
4. Do not import drawing, product, view, files, or legacy domain/application
   packages.

### Add or change file output

1. Keep public entry points in `src/cady/files/dxf.py`, `stl.py`, or `step.py`.
2. Require or preserve explicit `tolerance` on public render/write functions.
3. Add file-level regression tests under `tests/files/`.
4. Check import boundary tests after changing module-scope imports.

### Update docs or examples

Use current suffixless names. Do not add new examples using `Line2D`, `Body3D`,
`Drawing2D`, `line2d`, or similar old spelling unless the API itself changes.
Use tuple points, not nonexistent `Vec2`/`Vec3` classes.

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
  and numeric mesh helpers
- `tests/measurement/`: distance, intersection, and future measurement queries
- `tests/drawing/`: drawings, layers, dimensions, entities
- `tests/product/`: parts, assemblies, flattening
- `tests/view/`: scene model and viewer smoke coverage
- `tests/vessels/`: linesplan import, sampling, and meshing behavior
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
