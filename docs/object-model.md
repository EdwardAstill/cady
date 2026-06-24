# Object Model

## Overview

cady has two kinds of objects:

- authoring objects, which preserve CAD meaning;
- evaluated objects, which hold sampled points, polygons, meshes, and
  transforms for calculation or output.

Most user code should create authoring objects, organise them in a `Model`,
and let cady convert to evaluated geometry only at explicit boundaries.

## Details

## Object Hierarchy

```text
Model
  metadata -> ModelMetadata
  drawings -> Drawing2D values, by name
    Drawing2D
      layers -> ModelLayer values, by name
        ModelLayer
          shapes -> Shape2D values
      annotations -> text, hatches, blocks, inserts, dimensions
  parts -> Part values, by name
    Part
      solids -> Shape3D values
  assemblies -> Assembly values, by name
    Assembly
      part references -> Part names
```

`Drawing2D`, `Part`, and `Assembly` are peers under `Model`. A drawing does
not contain parts, and a part does not contain drawings. A drawing is for 2D
DXF-style output; a part is for 3D STL/STEP-style output; an assembly is a
named list of part references.

## Creation Flow

Factory functions create shapes. Model methods create or return containers.
Shapes are then added to the right container:

```text
line(...) / circle(...) / rectangle(...) / polyline(...) / spline(...)
  -> Shape2D
      -> model.drawing("name").layer("LAYER").add(shape)
      -> shape.to_array(tolerance=...) for numeric 2D work

shape2d.extrude(...) / prism(...) / sphere(...)
  -> Shape3D
      -> model.part("name").add(solid)
      -> solid.to_array(tolerance=...) for numeric 3D work

model.assembly("name").add(part)
  -> stores the part name, not a copy of the part geometry
```

The common path looks like this:

```python
from cady import Model, circle, rectangle

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
solid = profile.extrude("+z", 0.04)

model = Model("plate")
model.drawing("front").layer("PLATE").add(profile)
model.part("plate").add(solid)
```

## Authoring Objects

`Vec2` and `Vec3` are coordinate values. Factories accept plain tuples and
promote them to vectors.

`Shape2D` objects are 2D geometry:

- `Line` and `Arc` are open curves;
- `Circle`, `Rectangle`, and closed `Polyline` values are closed profiles;
- `Spline` stores Bezier control points;
- `Path` joins open segments into one curve.

Closed 2D shapes can carry holes:

```python
profile = rectangle((0, 0), (1, 0.6)).with_hole(circle((0.5, 0.3), 0.1))
```

Closed 2D shapes can become 3D solids:

```python
solid = profile.extrude("+z", 0.04)
```

`Shape3D` objects are 3D geometry:

- `Prism` is a box-like solid;
- `Sphere` is a spherical solid;
- `Extrusion` is a closed 2D profile swept along an axis;
- `Revolution` is a profile revolved around an axis.

Geometry values are immutable. Transforms and composition methods return new
geometry instead of changing the original.

## Model Containers

`Drawing2D` is for 2D output. It contains named layers, and those layers hold
2D shapes. Drawings can also contain text, hatches, blocks, inserts, and
dimensions.

```python
front = model.drawing("front")
front.layer("PLATE", color=7).add(profile)
front.layer("SECTION").hatch(profile)
front.add_text("PLATE", at=(0.02, 0.02), height=0.03)
```

`Part` is for 3D output. It contains solids:

```python
model.part("plate").add(solid)
```

`Assembly` stores named part references for model organisation. It is not a
boolean engine or a placement system.

`Model` is the public top-level container. It owns drawings, parts,
assemblies, and metadata, and exposes the main writers:

```python
model.write_dxf("plate.dxf")
model.write_stl("plate.stl")
model.write_step("plate.step")
```

## Evaluated Objects

Evaluated objects live in `cady.numeric`. They are useful once geometry needs
to become arrays:

- `ArrayPolyline2` stores sampled 2D vertices;
- `ArrayPolygon2` stores a filled outer loop and holes;
- `ArrayMesh3` stores vertices and triangular faces;
- `Transform2` and `Transform3` store matrix transforms.

Create evaluated geometry explicitly:

```python
profile_array = profile.to_array(tolerance=1e-3)
mesh = solid.to_array(tolerance=1e-3)
```

Tolerance matters because circles, arcs, splines, spheres, extrusions, and
revolutions need sampling before they can become polylines or meshes.

## File Objects

Use `Model` first. Lower-level file objects exist for one-format workflows:

- `DxfDrawing` is a direct DXF scene object;
- `StlMesh` is a direct STL triangle collector;
- `cady.files.dxf`, `cady.files.stl`, and `cady.files.step` expose format
  facades.

DXF preserves semantic 2D entities where possible. STL always uses triangles.
STEP export uses supported semantic solids instead of numeric meshes.

## Creation Rules

Use factories for normal construction:

```python
from cady import circle, line, prism, rectangle, sphere
```

Use direct classes when you need exact class-level control or when extending
cady internals.

Stay semantic while building geometry. Convert with `to_array(...)` only for
numeric calculation, plotting, visualisation, tessellation, or mesh output.
