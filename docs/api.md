# API Guide

## Overview

Import common authoring objects from `cady`. Import subpackages when you need
file facades, numeric types, transforms, plotting, or visualisation.
For the higher-level relationship between objects, see
[Object model](object-model.md).

## Details

## Object Relationships

Use `Model` as the top-level object when one source should produce drawings,
meshes, and solid exports:

```text
Model
  -> Drawing2D
      -> Layer
          -> Shape2D: Line, Arc, Circle, Rectangle, Polyline, Spline, Path
      -> text, hatches, blocks, inserts, dimensions
  -> Part
      -> Shape3D: Prism, Sphere, Extrusion, Revolution
  -> Assembly
      -> named Part references
```

The authoring objects are semantic. A `Circle` is still a circle, an
`Extrusion` still knows its profile and distance, and a `Drawing2D` still knows
its layers. Convert with `to_array(tolerance=...)` only when numeric geometry
is needed for plotting, tessellation, mesh processing, or STL-style output.

## Object Glossary

`Shape2D` is the base type for 2D authoring geometry. Concrete shapes include
`Line`, `Arc`, `Circle`, `Rectangle`, `Polyline`, `Spline`, and `Path`.
Closed 2D shapes can carry holes and can be extruded into 3D solids.

`Shape3D` is the base type for 3D authoring geometry. `Prism` and `Extrusion`
are supported by STEP export; `Sphere` and `Revolution` can be tessellated for
STL, plotting, and viewing.

`Drawing2D` groups 2D entities for DXF output. It contains named layers plus
drawing annotations such as text, hatches, blocks, inserts, and dimensions.

`Part` groups 3D solids for STL and STEP output.

`Assembly` stores named part references. It is model organisation, not a
boolean or placement engine.

`Model` is the preferred public container. It owns named drawings, parts,
assemblies, and metadata, and provides `write_dxf`, `write_stl`, and
`write_step`.

`DxfDrawing` and `StlMesh` are lower-level format objects. Use them directly
only when you are working with one format rather than a model.

`ArrayPolyline2`, `ArrayPolygon2`, `ArrayMesh3`, `Transform2`, and
`Transform3` are numeric objects. They represent evaluated geometry and matrix
operations, not authoring intent.

## Common Imports

```python
from cady import Model, circle, line, prism, rectangle, sphere
from cady.files import dxf, step, stl
from cady.numeric import Transform3
```

## Factories

2D:

- `line((x1, y1), (x2, y2))`
- `arc((cx, cy), radius, start_rad, end_rad)`
- `circle((cx, cy), radius)`
- `rectangle((x, y), (width, height))`
- `polyline(points, closed=False)`
- `spline(control_points)`

3D:

- `sphere((x, y, z), radius)`
- `prism((x, y, z), (dx, dy, dz))`

Closed 2D shapes can be extruded:

```python
solid = rectangle((0, 0), (1, 0.5)).extrude("+z", 0.04)
```

## Model API

```python
model = Model("plate")
model.drawing("front").layer("PLATE").add(profile)
model.part("plate").add(profile.extrude("+z", 0.04))
```

Useful methods:

- `model.drawing(name)` and `model.part(name)` create or return named groups;
- `model.write_dxf(path, tolerance=...)` writes drawings;
- `model.write_stl(path, ascii=False, tolerance=...)` writes part meshes;
- `model.write_step(path)` writes supported solids;
- `model.to_array(tolerance=...)` returns part meshes;
- `model.drawing_arrays(tolerance=...)` returns drawing arrays.

## Drawing API

```python
front = model.drawing("front")
front.layer("PLATE", color=7).add(profile)
front.layer("SECTION").hatch(profile, pattern="ANSI31", scale=0.025)
front.add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
```

Drawings also support blocks, inserts, linear/aligned/radius/diameter
dimensions, angular dimensions, layer colours, and linetypes.

## File Facade

```python
dxf.write_model(model, "plate.dxf", tolerance=1e-3)
stl.write_model(model, "plate.stl", tolerance=1e-3)
step.write_model(model, "plate.step")

drawing = dxf.read_drawing("profile.dxf")
mesh = dxf.read_mesh("faceted.dxf")
faces = step.read_faces("member.step")
```

## Errors

```python
from cady import CadError, ReadError, SceneError, WriteError
```

Use `SceneError` for invalid model composition, `ReadError` for read failures,
and `WriteError` for writer failures.
