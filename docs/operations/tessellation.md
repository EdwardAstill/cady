# Tessellation

Tessellation is the explicit boundary where analytic or semantic geometry
becomes sampled vertices, polygons, triangles, or meshes.

cady keeps this boundary visible because tolerance and output format matter.
A `Circle` should stay a circle while a user is authoring a drawing. It should
become points only when plotting, triangulating, meshing, exporting to STL, or
performing numeric analysis.

## Tolerance

Most tessellation entry points accept `tolerance`. It is a geometric error
budget measured in model units. Smaller values create denser output; larger
values create coarser output.

Examples:

- circle and arc sampling chooses enough segments to stay within tolerance;
- spline sampling uses tolerance to choose sample density;
- extrusion and revolution meshing use tolerance for curved profile and sweep
  discretisation;
- sphere meshing uses tolerance to choose latitude/longitude density.

Use the loosest tolerance that is accurate enough for the task. Visual
preview meshes usually tolerate coarser values than final STL output.

## 2D Conversion

`Shape2D.to_array(tolerance)` converts semantic 2D geometry into numeric
objects:

- `Line` and open `Polyline` become `ArrayPolyline2`;
- `Arc`, `Circle`, and `Path` sample curved parts according to tolerance;
- closed profiles become `ArrayPolygon2` where fill or holes matter;
- holes are converted through their own `to_array(...)` path.

The result is suitable for plotting, polygon operations, hatch preparation,
or later 3D meshing.

## Splines

`Spline` is represented by cubic Bezier control points. Numeric code can keep
those control points as `ArrayBezierSpline2` without sampling.

Sampling is explicit:

```python
array_spline = spline.to_array(tolerance=1e-3)
polyline = array_spline.sample(tolerance=1e-3)
```

This keeps design intent available for as long as possible and avoids
accidental loss of curve information.

## 3D Conversion

`Shape3D.to_array(tolerance)` converts semantic solids into `ArrayMesh3`:

- `Prism` meshes directly from its box corners;
- `Extrusion` tessellates the profile, caps it, and connects side faces;
- `Revolution` samples the profile and sweep angle into rings;
- `Sphere` samples latitude and longitude rings.

`Part.to_array(tolerance)` and `Model.to_array(tolerance)` collect meshes from
their contained solids for visualisation and numeric processing.

## Existing Export Paths

DXF, STL, and STEP output should remain compatible while numeric internals are
introduced.

DXF is semantic where possible: circles, arcs, hatches, dimensions, text,
blocks, inserts, and layers should still emit as DXF entities rather than
losing meaning to generic polylines unless the format path requires it.

STL is mesh-based by definition. It can use `ArrayMesh3` internally, with
adapters such as:

```python
array_mesh_to_triangles(mesh)
triangles_to_array_mesh(triangles)
```

to preserve compatibility with tuple-based triangle APIs during migration.

STEP export should continue to use supported semantic B-rep solids. Numeric
meshes are useful for preview and STL, but they should not replace STEP
topology where cady has semantic solids available.

## Practical Guidance

Use semantic shapes for model construction:

```python
profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
solid = profile.extrude("+z", 0.04)
```

Convert only at the boundary:

```python
profile_array = profile.to_array(tolerance=1e-3)
mesh = solid.to_array(tolerance=1e-3)
```

Use the same tolerance consistently when comparing mesh counts, bounds, or
visual output.
