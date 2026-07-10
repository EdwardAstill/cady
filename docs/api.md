# API reference

The top-level `cady` package exposes the common authoring values. More focused
helpers remain in their owning subpackages.

## Geometry

| Name | Description |
|---|---|
| `Point2`, `Point3` | Immutable positions with named coordinates and affine arithmetic. |
| `Vector2`, `Vector3` | Immutable directions and displacements. |
| `Line2`, `Line3` | Straight line segments. |
| `Arc2`, `Arc3` | Circular arcs defined by center, start, and midpoint. |
| `Spline2`, `Spline3` | Cubic Bezier splines, optionally built from endpoint tangent vectors. |
| `Polyline2`, `Polyline3` | Open or closed polyline and curve sequences. |
| `Circle2`, `Ellipse2` | Closed 2D conic curves. |
| `Region2`, `Region3` | Filled 2D regions and surface-placed regions. |
| `Surface2`, `Surface3` | Parametric surfaces. |
| `Plane3` | Local coordinate plane in 3D. |
| `Mesh2`, `Mesh3` | Indexed polygon meshes. |
| `Wireframe3` | Edge-only 3D topology. |
| `PointCloud2`, `PointCloud3` | Unconnected point collections. |
| `Body3` | Immutable feature-history body. |
| `Curve2`, `Curve3` | Curve protocols used by polyline composition. |

Geometry constructors accept plain `(x, y)` and `(x, y, z)` coordinate
sequences as well as `Point2`/`Point3` values. Semantic geometry exposes points
and directions as immutable point and vector values; numeric and file boundaries
remain sequence-oriented.

```python
point = Point3(1.0, 2.0, 3.0)
offset = Vector3(0.0, 0.0, 2.0)
moved = point + offset
direction = moved - point
```

Point arithmetic follows affine rules: subtracting points produces a vector,
and adding or subtracting a vector produces a point. Vectors support length,
normalization, dot products, scaling, and vector arithmetic; `Vector3` also
supports cross products. Equality remains exact, with geometric tolerances kept
in explicit measurement and operation APIs.

Common constructors include:

```python
Line2(start, end)
Arc2(center, start, midpoint)
Circle2(center, radius)
Polyline2(items, closed=False)
Spline2(points, vectors=None, closed=False)
Plane3(point, normal, x_axis=None)
Region2.rectangle(width, height, origin=(0.0, 0.0))
Region2.circle(radius, center=(0.0, 0.0))
Body3.box(width=..., depth=..., height=...)
Body3.cylinder(radius=..., height=...)
Body3.sphere(radius=..., center=(0.0, 0.0, 0.0))
```

## Drawing and product values

Top-level drawing exports are `Drawing2`, `DrawingEntity`, `Layer`, `Text2`,
`Hatch2`, `Insert2`, `BlockDefinition`, `DimStyle`, and the suffix-`2`
dimension values.

Product exports are `Part`, `PartInstance`, `Assembly`, `AssemblyInstance`, and
`Material`. `Document` is the optional registry for named drawings, products,
and scenes.

## View values

Top-level view exports include `Scene`, `SceneObject`, `Camera`, the light
values, `DisplayStyle`, and scene overlays. Backend-independent preparation is
available from `cady.view`:

```python
from cady.view import RenderScene, SceneLine, SceneMesh, prepare_scene
```

`view_scene` and `view_lines` are imported lazily when requested.

## Operations and measurements

`cady.operations` exports `Transform2`, `Transform3`, triangulation, mesh
clipping helpers, and `sphere_triangles`. Mesh construction, statistics, and
topology helpers live in `cady.operations.mesh` modules.

`cady.measurement` owns object-level `distance(...)` and `intersection(...)`
queries and their result records.

## File I/O

```python
from cady.files import dxf, step, stl
```

| Function | Result or action |
|---|---|
| `dxf.read(path)` | Returns a `DxfImportResult`. |
| `dxf.read_drawing(path)` | Returns a `Drawing2`. |
| `dxf.read_curves(path)` | Returns imported 3D wire-curve records. |
| `dxf.read_mesh(path)` | Returns a `Mesh3` from DXF mesh entities. |
| `dxf.read_wireframe(path)` | Returns merged imported wires as `Wireframe3`. |
| `dxf.write(drawing, path, *, tolerance)` | Writes DXF R2018. |
| `stl.write(target, path, *, ascii, tolerance)` | Writes binary or ASCII STL. |
| `step.write(target, path, *, tolerance)` | Writes mesh-oriented STEP. |
| `step.read_mesh(path)` | Returns elementary STEP faces as a `Mesh3`. |
| `step.read_faces(path)` | Returns parsed elementary face records. |
| `step.read_members(path)` | Returns extracted simple extruded members. |

## Errors

`CadError` is the shared base. The public specialisations are `GeometryError`,
`DrawingError`, `ProductError`, `ViewError`, `ReadError`, and `WriteError`.
