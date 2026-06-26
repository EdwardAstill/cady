# Geometry Package Restructure Spec

## Goal

Move semantic geometry objects into one `cady.geometry` package, rename
`cady.ops` to `cady.operations`, and move ergonomic constructor functions into
`cady.operations`.

This is an internal organisation change. It must not change object behaviour,
file output, mesh output, public top-level `cady` exports, or tolerance
semantics.

## Non-Goals

- Do not merge numeric array types into semantic geometry objects.
- Do not change public object names.
- Do not change geometry behaviour, validation rules, or generated meshes.
- Do not remove compatibility packages in the same migration.
- Do not start a broader CAD-kernel rewrite.

## Target Shape

```text
cady/
  geometry/
    __init__.py
    line2d.py
    arc2d.py
    polyline2d.py
    conic2d.py
    profile2d.py
    frame3d.py
    face3d.py
    body3d.py
    mesh2d.py
    mesh3d.py
    wireframe3d.py
    features.py

  operations/
    __init__.py
    curves2d.py
    profiles.py
    triangulation.py
    meshes3d.py
    mesh_cut.py
    transforms.py

  constructor helpers/
    __init__.py
    curves2d.py
    profiles.py
    primitives3d.py
```

`operations` owns NumPy-backed evaluated arrays, transforms, validation, and
bounds.

## Dependency Rules

Allowed:

```text
cady.__init__ -> geometry, constructor helpers, operations, drawing, product, view
constructor helpers -> geometry
geometry -> operations
geometry -> vec/errors/utils
operations -> vec/errors/utils when useful
```

Forbidden:

```text
operations -> geometry
operations -> drawing/product/view/files/visualisation
geometry -> visualisation at module scope
```

## Current Audit

Current object packages:

- `geometry2d/curves.py` contains `Curve2D`, `ClosedCurve2D`, `Line2D`,
  `Arc2D`, `Spline2D`, `Polyline2D`, `Circle2D`, `Ellipse2D`, and
  `ClosedPolyline2D`.
- `geometry2d/profile.py` contains `Profile2D`.
- `geometry2d/mesh.py` contains `Mesh2D`.
- `geometry2d/constructor helpers.py` contains 2D curve/profile constructor helpers.
- `geometry3d/body.py`, `face.py`, `frame.py`, `mesh.py`, `wireframe.py`,
  `curves.py`, `features.py`, and `constructor helpers.py` are already split by object
  family.
- `geometry3d/_mesh_builders.py` builds semantic `Mesh3D` values and imports
  geometry classes, so it cannot move into `operations` unchanged.
- `ops/` is already mostly object-agnostic and should become `operations/`.
- NumPy-backed array and transform helpers live in `operations`.

Large files that should not grow further during migration:

- `geometry3d/wireframe.py`: 728 lines.
- `ops/mesh_cut.py`: 613 lines.
- `geometry3d/mesh.py`: 477 lines.
- `geometry2d/curves.py`: 322 lines.

Compatibility surface:

- `src/cady/__init__.py` re-exports from `geometry2d`, `geometry3d`, and
  `operations`.
- `files`, `product`, `visualisation`, docs, examples, and tests import
  `cady.geometry2d`, `cady.geometry3d`, and `cady.ops`.
- Convention tests explicitly check `geometry2d`, `geometry3d`, and
  `ops` import boundaries; these tests must be updated to cover `geometry`,
  `operations`, and `constructor helpers`.

Audit caveat:

- Tests reference `cady.ops.linesplan`, but no `src/cady/ops/linesplan.py` was
  present in the audited tree. Verify whether this is an in-progress local
  change before executing the migration.

## Comparison

### Optimal

- The existing semantic/evaluated boundary is sound: geometry objects convert
  to numeric arrays or meshes through explicit tolerances.
- Operation-owned array/transform helpers avoid importing authoring packages.
- `ops` already mostly follows the desired object-agnostic direction.
- Top-level `cady` exports provide a stable public API and should remain the
  main user-facing import path.

### Close

- `geometry3d` is already mostly object/file based, but it should move under
  `geometry`.
- `geometry2d` has the right objects, but `curves.py` should be split into
  object-family files.
- Existing constructor helper files already have the right responsibility, but should move
  out of geometry packages.

### Different

- Current top-level package names encode dimensionality (`geometry2d`,
  `geometry3d`) instead of object role (`geometry`, `constructor helpers`,
  `operations`).
- `ops` should be renamed to `operations` for readability.
- `geometry3d/_mesh_builders.py` mixes algorithm work with semantic object
  construction. Split primitive algorithm pieces into `operations` and keep
  semantic `Mesh3D` assembly in geometry methods or a private geometry helper.

### Dead / Stale Risk

- Any stale references to `cady.ops.linesplan` must be resolved before or
  during the rename.
- Old package names should not be deleted in the first migration; they should
  become compatibility shims.

## Practical Target

Use a staged migration instead of a single large move:

1. Add new packages and re-export from old packages.
2. Move object modules into `geometry`.
3. Move constructor helpers into `constructor helpers`.
4. Rename `ops` to `operations` with a compatibility shim.
5. Update first-party imports to the new names.
6. Update docs/tests/convention rules.
7. Only later, in a breaking-change plan, remove shims.

This keeps the migration reviewable and allows tests to catch import-boundary
mistakes after each phase.

## Done Criteria

- `from cady import Line2D, Body3D, Mesh3D, box, profile_rectangle` still works.
- New imports work:
  - `from cady.geometry import Line2D, Body3D, Mesh3D`
  - `from cady.operations import line2d, profile_rectangle, box`
  - `from cady.operations import cut_mesh_by_plane`
- Old compatibility imports still work during this migration:
  - `from cady.geometry2d import Line2D`
  - `from cady.geometry3d import Body3D`
  - `from cady.ops import cut_mesh_by_plane`
- `operations` does not import `cady.geometry`.
- Operation-owned array/transform helpers do not import semantic geometry or
  authoring packages.
- Runtime dependency allowlist remains unchanged.
- Full tests, pyright, ruff, `git diff --check`, and `git status` pass with
  expected changes only.
