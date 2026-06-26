# Ideal Architecture: Geometry Package Restructure

## Purpose

Make cady's geometry model easier to navigate by collecting semantic geometry
objects under one `cady.geometry` namespace, while preserving the existing
separation between authoring objects, object-agnostic operations, and
constructor helpers.

## Inputs

- User-authored geometry objects: 2D curves, profiles, 3D frames, faces,
  bodies, meshes, and wireframes.
- Constructor inputs: tuples, vectors, dimensions, radii, primitive parameters, and
  optional frames.
- Operation inputs: numeric primitives, arrays, coordinates, faces, edges,
  tolerances, and plane definitions.

## Outputs

- Stable public imports from `cady`.
- A clearer internal layout:

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
    curves2d.py
    profiles.py
    triangulation.py
    meshes3d.py
    mesh_cut.py
    transforms.py

  constructor helpers/
    curves2d.py
    profiles.py
    primitives3d.py
```

- Existing file exporters, drawing objects, product objects, view objects, and
  docs should continue to work through public APIs.

## Invariants

- Geometry objects remain immutable frozen dataclasses.
- Every sampling or evaluation method keeps explicit `tolerance`.
- `geometry` contains semantic objects and object methods.
- `operations` contains object-agnostic algorithms and must not import
  `cady.geometry`.
- `constructor helpers` may import `cady.geometry` and build valid objects from ergonomic
  user inputs.
- `geometry` may call `operations`, but operations must work on primitive
  values, vectors, arrays, faces, edges, and scalars.
- The runtime dependency boundary remains intact: core authoring modules do not
  import visualization packages at module scope.

## Ideal Dependency Direction

```text
cady public API
        |
        v
constructor helpers  ----->  geometry  ----->  operations  ----->  numeric arrays/helpers
                         \                         \
                          \                         -> stdlib/math
                           -> vec/errors
```

Rules:

- `constructor helpers` are convenience constructors only.
- `geometry` owns object identity, validation, domain methods, and conversions.
- `operations` owns reusable algorithms such as discretisation, triangulation,
  mesh cutting, mesh merging, and point transforms.
- `operations` owns the lower-level array/evaluated-data layer after the
  numeric package removal. This plan should not conflate semantic `Mesh3D`
  with array mesh buffers.

## Naming

- Rename `cady.ops` to `cady.operations`.
- Create `cady.operations` for constructor helpers instead of placing constructor helpers
  inside geometry object modules.
- Prefer object files for substantial classes and grouped files for tightly
  related variants:
  - `conic2d.py`: `Circle2D`, `Ellipse2D`
  - `polyline2d.py`: `Polyline2D`, `ClosedPolyline2D`
  - `features.py`: feature record dataclasses

## Compatibility Position

The target internal structure can change without forcing users to update common
imports. The top-level `cady` exports should stay stable during the migration.

Short-term compatibility shims may remain for:

- `cady.geometry2d`
- `cady.geometry3d`
- `cady.ops`

These should re-export from the new modules and can be removed in a later
breaking-change plan.
