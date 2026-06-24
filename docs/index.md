# cady Documentation

cady is organised around small immutable value objects. Build the object you
need directly, convert to arrays or meshes only at explicit boundaries, and use
the file facades for DXF, STL, and STEP I/O.

## Start here

| Page | Covers |
|---|---|
| [Getting started](getting-started.md) | Install, first drawing/part, file output, and reads. |
| [Object model](object-model.md) | How geometry, drawings, parts, assemblies, scenes, and documents relate. |
| [API guide](api.md) | Public imports, constructors, methods, and file facades. |
| [File formats](files/index.md) | Supported DXF, STL, and STEP behavior. |
| [Examples](examples.md) | Runnable scripts and generated outputs. |
| [Architecture](architecture.md) | Package boundaries and conversion flow. |
| [Development](development.md) | Setup, gates, and contribution rules. |
| [Visualisation](visualisation.md) | Current scene/view model and example viewer artifacts. |

## Core idea

Use semantic objects while authoring:

```python
from cady import Drawing2D, Part, Profile2D, circle2d, profile_rectangle
```

Convert only when an operation needs evaluated geometry:

```text
Profile2D.to_array(tolerance=...) -> ArrayPolygon2
Body3D.to_mesh(tolerance=...)     -> Mesh3D
Part.to_mesh(tolerance=...)       -> ArrayMesh3
```

Use `Document` only when you want one named registry of drawings, parts,
assemblies, and scenes. It is not required for ordinary authoring or export.
