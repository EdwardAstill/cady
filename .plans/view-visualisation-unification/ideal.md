# View and Visualisation Unification Ideal

## Purpose

The subsystem has two jobs:

- Represent backend-independent scene intent: targets, cameras, lights, display
  styles, object visibility, and placement.
- Optionally render or prepare that scene with external visualisation backends.

The public authoring surface should feel like one package, while renderer
dependencies remain optional and lazy.

## Inputs

- Domain targets: 3D bodies, parts, assemblies, meshes, wireframes, drawings,
  and documents.
- Scene data: cameras, lights, display styles, object references, transforms.
- Renderer selection and renderer-specific options.
- Explicit geometry tolerances for evaluated mesh/path conversion.

## Outputs

- Immutable scene value objects.
- Prepared render data suitable for a backend.
- Optional backend viewer calls such as mesh, line, target, and scene viewing.

## Invariants

- Core authoring imports stay import-light.
- Optional packages such as vispy, matplotlib, and pyvista must not load at
  `import cady` or normal scene-authoring time.
- Scene/value types remain frozen dataclasses where applicable.
- Conversion to numeric mesh/path data happens at explicit rendering/export
  boundaries with a required tolerance.
- Existing public APIs should either continue to work or have a narrow,
  deliberate compatibility shim.

## Ideal Boundary

`cady.view` should be the single public package for both scene description and
optional viewing:

- `cady.view.scene`, `camera`, `light`, `style`, and `open_view` own immutable
  scene values.
- `cady.view.rendering` or equivalent owns backend-independent preparation
  records and conversion orchestration.
- `cady.view.backends.<backend>` owns imports of optional renderer libraries.
- `cady.view` re-exports both scene values and lazy viewer functions.

## Dependency Direction

```text
domain objects -> scene values -> prepare/render orchestration -> backend adapter
```

The reverse direction is not allowed. Scene values must not import backend
adapters. Backend adapters can depend on scene values and numeric conversion.

## Error Handling

- Scene construction errors should use `ViewError`.
- Missing optional renderer packages should produce clear `ImportError` or
  `ViewError` messages at the call site, not import time for `cady.view`.

## Practical Target

The smallest valuable refactor is to make `cady.view` the canonical home for
viewer helpers, move implementation files under that package, and remove the
old separate package. Tests should enforce that optional viewer dependencies
remain lazy.
