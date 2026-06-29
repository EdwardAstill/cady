# Common Geometry Object API

Most geometry objects should share a small API: cheap geometric queries,
explicit conversion methods, and immutable transform helpers. The methods are a
convention, not a base class contract. Add them when the operation has a clear
meaning for that geometry type.

## Hierarchy

  ├─ 2D geometry
  │  ├─ Curves: Line2, Arc2, Spline2, Polyline2, Circle2, Ellipse2
  │  ├─ Filled regions: Region2
  │  ├─ Meshes: Mesh2
  │  └─ Points: PointCloud2
  ├─ 3D geometry
  │  ├─ Curves: Line3, Arc3, Spline3, Polyline3
  │  ├─ Frames and surfaces: Plane3, Surface2, Surface3
  │  ├─ Surface regions: Region3
  │  ├─ Meshes: Mesh3, Wireframe3
  │  ├─ Points: PointCloud3
  │  └─ Bodies: Body3


## Object Roles

The objects split into three layers:

| Layer | Role |
|---|---|
| Point tuples | Small coordinate values used to place geometry. |
| Semantic geometry | Curves, regions, surfaces, point clouds, meshes, and bodies. |
| Numeric boundaries | Arrays and triangle meshes created only when sampling, meshing, export, or viewing needs them. |

The important rule is that authoring objects should stay semantic. A circle is a
centre plus radius until `to_array(tolerance=...)` samples it; a body is feature
history until `to_mesh(tolerance=...)` evaluates it. The current codebase uses
plain point tuples for coordinates rather than dedicated vector classes.

### Line2 and Line3

`Line2` and `Line3` are finite straight segments between two distinct endpoints.
They are not infinite mathematical lines.

Their `points()` are just the start and end points. Their `bounds()` are cheap
because a straight segment's axis-aligned bounds come directly from those two
points. `to_array(tolerance=...)` returns the endpoints as numeric point data;
the tolerance is accepted to keep the conversion boundary consistent, even
though a line does not need discretisation.

Use `Line2` for planar sketch and drawing edges. Use `Line3` for spatial edges,
wire paths, and curve segments inside 3D polylines.

### Arc2 and Arc3

`Arc2` and `Arc3` are circular arc segments. They store the circle centre,
radius, start angle, and end angle; `Arc3` also stores the local perpendicular
axes that define the arc plane.

An arc is still analytic while authored. `points()` returns its two endpoints,
not every point along the curve. `to_array(tolerance=...)` is the sampling
boundary where the curved arc becomes a polyline approximation.

Use `Arc2` for planar circular segments. Use `Arc3` when the same circular
segment needs to live in an arbitrary 3D plane.

### Spline2 and Spline3

`Spline2` and `Spline3` are cubic Bezier spline paths. They are defined by
`3n + 1` control points, so every segment has a start point, two handles, and
an end point.

The control points are the authored shape. `points()` returns those control
points, while `to_array(tolerance=...)` adaptively samples the curve into
points. This keeps editable spline data separate from the numeric approximation
used by meshing, export, or display.

`Spline2` can be marked closed. `Spline3` represents an open 3D spline path in
the current source shape.

### Polyline2 and Polyline3

`Polyline2` is a 2D path made from straight segments between stored vertices. It
can be open or closed. A closed `Polyline2` can become a `Mesh2`; an open one
stays a curve.

`Polyline3` is a 3D path that can be built from vertices or from curve objects
such as `Line3`, `Arc3`, and `Spline3`. When it contains curved segments,
`discretise(tolerance=...)` or `to_array(tolerance=...)` samples those curves
into a point path.

Closed 3D polylines are meshable only when they are planar within the supplied
tolerance. That check matters because a triangle fill needs a stable plane.

### Circle2 and Ellipse2

`Circle2` and `Ellipse2` are closed 2D curves. They store compact analytic
parameters rather than many boundary points.

`Circle2` is a centre plus radius. `Ellipse2` is a centre, x radius, y radius,
and optional rotation. Both report `closed = True`, and both sample to arrays
only when a caller supplies `tolerance`.

Their `points()` methods return a stable repeated start point. That gives
callers a representative point without implying that the whole curve has been
sampled.

### Region2

`Region2` is a filled planar area. It has one closed outer boundary and zero or
more closed holes.

The boundary curves can stay semantic: a circular region can keep a `Circle2`
outer loop instead of immediately becoming polygon vertices. `loops(tolerance=...)`
is the boundary where those curves become sampled 2D loops.

Use `Region2` for sketch profiles, filled drawing areas, and body features that
start from a planar profile.

### Mesh2

`Mesh2` is an indexed 2D triangle mesh. It stores vertices, triangular faces,
and optional edges.

This is already numeric-style topology, so it belongs near conversion
boundaries. A closed `Polyline2` or `Region2` can produce mesh data, but the
mesh itself should not pretend to be the original semantic curve or region.

`triangles` expands face indices into point triples. `boundary_loops` derives
open mesh boundaries from topology when faces are present.

### PointCloud2

`PointCloud2` is a collection of unconnected 2D points. It has no edges, faces,
curve order, or filled area.

Use it when the data is just samples or markers. It supports bounds, point
access, array conversion, and transforms, but it should not be treated as a
polyline or mesh unless another operation explicitly constructs that topology.

### Plane3

`Plane3` is a local 3D coordinate frame for planar work. It stores an origin,
an x-axis, and a normal; the y-axis is derived so the frame stays right-handed.

`point(u, v)` maps local plane coordinates into world 3D coordinates. That makes
`Plane3` the placement object for planar profiles, planar surfaces, and body
features.

The constructor normalises the axes and repairs the x-axis so it is orthogonal
to the normal. This keeps downstream projection and meshing code from carrying
invalid frames.

### Surface2 and Surface3

`Surface2` and `Surface3` are parametric surfaces. They map parameters `(u, v)`
to points.

`Surface2` maps into 2D and is useful for planar parameter-space work.
`Surface3` maps into 3D and can represent either a plane or a general
parametric surface. For plane surfaces, it keeps the underlying `Plane3` as
`base_plane`.

`Surface3.normal(u, v)` returns the analytic plane normal for planes, and a
finite-difference normal for general parametric surfaces. That keeps one
surface interface available to bounded surface regions.

### Region3

`Region3` is a bounded patch on a `Surface3`. Its `region` is a 2D parameter
domain, and its `surface` maps that domain into 3D.

For planar regions, `Region3.from_region(...)` can place a 2D region on a
`Plane3`. For point-based construction, `from_points(...)` and `convex_hull(...)`
fit a plane and create a projected parameter region.

`to_mesh(tolerance=...)` is the evaluation boundary. The region remains a
surface patch until the caller asks for triangles.

### Mesh3

`Mesh3` is an indexed 3D triangle mesh with optional display edges. It stores
vertices, triangular faces, and edge indices.

Use it for evaluated geometry: imported mesh data, exported mesh data, rendered
surfaces, and body results after `to_mesh(tolerance=...)`. It is not a feature
history and does not remember whether it came from a box, cylinder, region, or
surface patch.

Transforms return new meshes. Mirroring also reverses face winding so normals
remain consistent after reflection.

### Wireframe3

`Wireframe3` is edge-only 3D topology. It can be built from polylines or from
indexed vertices and edges.

A wireframe has vertices and edges but no faces. It is useful for imported line
geometry, section networks, sketch-like 3D paths, and workflows that need to
split crossing edges or remove dangling branches before triangulation.

`to_mesh(tolerance=...)` is an explicit conversion. Until then, the object
represents connected lines, not surfaces.

### PointCloud3

`PointCloud3` is a collection of unconnected 3D points. It stores spatial sample
positions without edges, faces, or curve order.

Use it for measured points, markers, and point-only views. It supports bounds,
array conversion, transforms, mirroring, and point rendering, but any curve,
wireframe, or mesh topology must be created by a separate operation.

### Body3

`Body3` is a semantic 3D solid-like object built from an ordered feature
history. The body records what it is made from instead of immediately baking
the result into triangles.

Current meshable paths include region extrusion and primitive bodies such as
boxes, cylinders, and spheres. Unsupported or record-only features can stay in
the history until an evaluator exists.

`transformed(...)` moves the feature data and returns a new body. `to_mesh(tolerance=...)`
is the boundary where all meshable features are evaluated and merged into a
`Mesh3`.

## Core Queries

| Member | Meaning | Applies to |
|---|---|---|
| `bounds()` | Axis-aligned `(min_point, max_point)` in the object's dimension. | Most finite geometry. |
| `boundary` | Convenience property that usually returns `bounds()`. | Most finite geometry. |
| `points()` | Authoring points or stable representative points. | Curves, polylines, regions, point clouds. |
| `point(...)` | Evaluate a parametric object at coordinates or parameters. | Surfaces and other parametric values. |
| `normal(...)` | Evaluate a surface normal. | 3D surfaces. |

`bounds()` should be cheap. It should inspect the analytic object or stored
vertices, not discretise a curve unless that is already the object's natural
representation. Empty finite collections should raise rather than invent a
zero-sized bound.

`points()` is not a tessellation promise. A line returns endpoints, an arc
returns start and end, a closed polyline returns a closing point, and a circle
can return a stable repeated start point.

## Topology Properties

| Property | Meaning | Applies to |
|---|---|---|
| `closed` | Whether a curve forms a closed loop. | Curves where closure changes behaviour. |
| `vertices` | Stored point sequence or indexed mesh points. | Polylines, meshes, point clouds, wireframes. |
| `faces` | Triangle indices into `vertices`. | Meshes. |
| `edges` | Edge indices into `vertices`. | Meshes and wireframes. |
| `triangles` | Expanded triangle point triples. | Meshes. |
| `boundary_loops` | Open boundary loops derived from mesh topology. | Meshes with faces. |

Do not add topology properties just to make objects look uniform. `closed`
belongs on `Circle2` and `Polyline2`; it does not need to exist on `Line2`.
`faces` belongs on a mesh, not on a curve that can only become a mesh after
sampling.

## Conversion Methods

| Method | Return | Boundary |
|---|---|---|
| `to_array(*, tolerance)` | NumPy point arrays or indexed arrays. | Semantic geometry to numeric data. |
| `to_mesh(*, tolerance)` | `Mesh2` or `Mesh3`. | Meshable geometry to triangles. |
| `loops(*, tolerance)` | Tuple of 2D loop arrays. | Filled 2D regions with holes. |
| `discretise(*, tolerance)` / `discretize(*, tolerance)` | Polyline-like geometry. | Curved paths to straight segments. |

Every sampling, meshing, and export path should take `tolerance` explicitly as
a keyword argument. This keeps discretisation visible at the call site.

`to_array(...)` is a numeric boundary, not a mutation method. Curves usually
return point arrays. Meshes and wireframes return `(vertices, faces, edges)`.

`to_mesh(...)` should only exist where the object is naturally meshable. Closed
polylines, regions, wireframes, meshes, and bodies can produce mesh data. Open
curves should stay curves.

## Transform Methods

Transforms should return new values and preserve semantic shape where possible.
A body transform should move feature planes instead of immediately baking the
body into a mesh.

| Method | 2D meaning | 3D meaning |
|---|---|---|
| `transformed(transform)` | Apply a `Transform2`. | Apply a `Transform3`. |
| `translate(...)` | Move by `(dx, dy)` or a 2D vector. | Move by `(dx, dy, dz)` or a 3D vector. |
| `rotate(...)` | Rotate by `angle` about a `centre` point. | Rotate by `angle` about an axis line. |
| `scale(...)` | Scale about a `centre` point. | Scale about a `centre` point. |
| `mirror(...)` | Reflect across a line, given a point and direction. | Reflect across a plane, given origin and normal. |

The rotate signatures should make the dimension difference visible:

```python
shape2.rotate(angle, centre=(0.0, 0.0))
shape3.rotate(angle, axis_origin=(0.0, 0.0, 0.0), axis_dir=(0.0, 0.0, 1.0))
```

For 3D objects, rotating about a line means rotating around
`axis_origin + t * axis_dir`. A helper can accept two axis points, but the
canonical transform should reduce to origin plus direction.

`mirror(...)` needs one extra rule for surface meshes: reflection reverses
orientation, so mesh implementations should reverse face winding to keep
normals consistent.

## Current Shape

| Object family | Common surface |
|---|---|
| Curves | `bounds()`, `boundary`, `points()`, `to_array(...)`. |
| Regions | `Region2` adds `loops(...)`; `Region3` meshes bounded surface regions. |
| Meshes | Indexed storage, `bounds()`, `boundary`, `to_array(...)`, transforms. |
| Point clouds | Point storage, `bounds()`, `points()`, `to_array(...)`, transforms. |
| Wireframes | Edge storage, transforms, cleanup, and triangulation helpers. |
| Bodies | Feature history, `transformed(...)`, `to_mesh(...)`, and `.view(...)`. |
| Surfaces | Parametric `point(...)`; `Surface3` also has `normal(...)`. |

The API should stay semantic until an explicit boundary: `to_array(...)`,
`to_mesh(...)`, file output, or viewer preparation.
