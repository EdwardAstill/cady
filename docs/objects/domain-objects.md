# Domain Objects

Domain objects are the semantic CAD layer. They are the objects users author
with, attach to drawings and parts, and export to file formats. They preserve
intent: a `Circle` stays a circle, a `Spline` keeps its Bezier control points,
and an `Extrusion` remembers its profile, axis, and distance.

Use domain objects when you want editable CAD geometry, readable model code,
DXF/STL/STEP output, or access to model organisation such as drawings, layers,
parts, assemblies, and metadata.

## 2D Shapes

The semantic 2D objects are:

- `Line(a, b)`
- `Arc(centre, radius, start_rad, end_rad)`
- `Circle(centre, radius)`
- `Rectangle(origin, size)`
- `Polyline(vertices, closed=False)`
- `Spline(control_points, closed=False)`
- `Path(segments, closed=False)`

Closed 2D shapes can carry holes through `with_hole(...)` or
`with_holes(...)`. Open shapes cannot carry holes because file writers and
tessellators need closed loops for filled regions.

`Shape2D.to_array(tolerance)` converts a semantic shape into numeric geometry:

- open lines, arcs, paths, and sampled curves become `ArrayPolyline2`;
- closed profiles become `ArrayPolygon2` where polygon semantics are needed;
- cubic Bezier splines can become `ArrayBezierSpline2` when the caller needs
  analytic control points rather than sampled vertices;
- holes are preserved as polygon holes or converted inner loops.

The conversion is explicit because tolerance controls discretisation. A circle
or arc is not flattened merely because NumPy is installed.

## 3D Shapes

The semantic 3D objects are:

- `Prism(origin, size)`
- `Sphere(centre, radius)`
- `Extrusion(profile, axis, distance)`
- `Revolution(profile, axis_origin, axis_direction, angle_rad)`

`Shape3D.to_array(tolerance)` converts a solid to an `ArrayMesh3`. The mesh is
the evaluated representation for plotting, STL output, intersections, volume
calculation, and bulk transforms. Semantic solids still remain the preferred
authoring API because they retain their original construction parameters.

## Drawings, Parts, and Models

`Drawing2D` groups 2D entities, text, hatches, blocks, inserts, dimensions,
and layers for DXF output. `Part` groups 3D solids for STL and STEP output.
`Model` is the preferred top-level object for named drawings, parts,
assemblies, and metadata.

Planned array conversion methods are:

```python
drawing.to_array(tolerance=1e-3)
part.to_array(tolerance=1e-3)
model.to_array(tolerance=1e-3)
```

`Drawing2D.to_array(...)` returns numeric 2D geometry for plotted drawing
entities. `Part.to_array(...)` returns a list of `ArrayMesh3` meshes, one per
solid or merged group depending on the implementation. `Model.to_array(...)`
returns the 3D part meshes for model-level visualisation and mesh processing.
If a caller needs drawing arrays from a model, use the named drawing conversion
surface rather than guessing whether `Model.to_array(...)` means 2D or 3D.

## When To Stay Semantic

Keep geometry semantic when:

- you are still editing design intent;
- exact shape type matters for DXF or STEP output;
- a spline should remain a spline rather than sampled points;
- layer, hatch, block, dimension, part, or assembly metadata matters;
- you are building an example or production model.

Convert with `to_array(...)` when:

- you need vectorised NumPy calculation;
- you need a sampled profile or mesh;
- you are plotting or viewing geometry;
- you are applying matrix transforms to many vertices;
- you are crossing into tessellation, meshing, or numerical analysis.

The intended boundary is:

```text
domain object.to_array(...) -> cady.ops primitive function -> cady.numeric result
```

Domain methods adapt object properties into primitive arguments. Core
operation functions should not receive domain objects.
