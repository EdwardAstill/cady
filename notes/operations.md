# Cady Operations

The operations package is the numeric layer between semantic CAD values and
meshable or array-backed results. It owns tuple coordinate math, local NumPy
conversion, transforms, polygon triangulation, mesh construction, mesh clipping,
capping, and lofting.

The important boundary is:

```text
semantic value -> to_array(tolerance=...) -> operation arrays
semantic value -> to_mesh(tolerance=...)  -> Mesh2 or Mesh3
operation helpers -> tuples, NumPy arrays, or existing semantic mesh values
```

`tolerance` is part of the algorithmic contract. Sampling, meshing,
triangulation, clipping, and tolerance-sensitive predicates all take it
explicitly instead of hiding a package-wide modelling resolution.

Sources:

- `src/cady/operations/coordinates.py`
- `src/cady/operations/transforms.py`
- `src/cady/operations/triangulation.py`
- `src/cady/operations/meshes.py`
- `src/cady/operations/__init__.py`

## Package Map

| Module | Role |
|---|---|
| `coordinates` | Pure tuple vector arithmetic in 2D and 3D. |
| `transforms` | Point transforms plus immutable homogeneous affine transform containers. |
| `triangulation` | Pure-Python polygon triangulation with ear clipping and hole bridging. |
| `meshes` | Mesh coercion, boundaries, caps, clipping, primitives, extrusion, lofts, linesplans. |
| `__init__` | Re-exports operations and lightweight semantic constructors. |

## Coordinate Operations

`coordinates.py` is the lowest-level tuple arithmetic layer. It avoids NumPy and
returns plain immutable tuples.

For 2D points or vectors:

$$
a + b = (a_x + b_x,\ a_y + b_y)
$$

$$
a - b = (a_x - b_x,\ a_y - b_y)
$$

$$
s a = (s a_x,\ s a_y)
$$

$$
a \cdot b = a_x b_x + a_y b_y
$$

$$
\lVert a \rVert = \sqrt{a \cdot a}
$$

$$
d(a,b) = \lVert a-b \rVert
$$

`normalised2(a)` returns `a / ||a||` and rejects zero-length vectors.

For 3D vectors the same addition, subtraction, scaling, dot product, length, and
distance rules apply. The extra operation is the cross product:

$$
a \times b =
\left(
a_y b_z - a_z b_y,
a_z b_x - a_x b_z,
a_x b_y - a_y b_x
\right)
$$

`is_parallel3(a, b, tolerance)` tests whether the cross-product magnitude is
near zero:

$$
\lVert a \times b \rVert^2 < \text{tolerance}^2
$$

`project_onto_line3(point, line_point, line_dir)` returns the scalar parameter
of the orthogonal projection onto a line:

$$
t = \frac{(p-p_0)\cdot d}{d\cdot d}
$$

The projected point is not returned by this helper; callers can reconstruct it
as `line_point + t * line_dir`.

## Local Array Conversion

There is no central `operations/arrays.py` module. Geometry values keep tuple
data while being authored, then convert to copied NumPy arrays only at explicit
boundaries such as `to_array(...)`, `to_mesh(...)`, transforms, and file/view
preparation.

When a module returns arrays, define the narrow type alias in that file, for
example `PointArray3: TypeAlias = NDArray[np.float64]`. Keep validation local
and minimal: public constructors and conversion boundaries should reject obvious
invalid input, but operation code should not be routed through broad validator
helpers just to satisfy type checking.

Bounds and exact curve length should live with the semantic object that owns the
geometry. Two-geometry queries such as distance and intersection belong in
`cady.measurement`, not `cady.operations`.

## Sampling

Curve sampling lives on the semantic curve objects that own the shape:
`Arc2`, `Arc3`, `Circle2`, `Ellipse2`, `Spline2`, and `Spline3` implement
`to_array(tolerance=...)` directly. `Arc2.discretise(...)` and
`Spline2.discretise(...)` return `Polyline2` values made from `Line2` segments.
Mesh-specific sampling, such as primitive segment counts, lives inside
`operations.meshes` next to the mesh algorithms that use it.

## Transform Operations

`transforms.py` has exactly two public objects: `Transform2` and `Transform3`.
Each object can be used in two ways:

```python
Transform2(points).rotate(angle).translate(dx, dy).array
Transform3(points).rotate(axis_dir=axis, angle=angle).translate(dx, dy, dz).array
```

or as a delayed transform when the points are not known yet:

```python
transform = Transform3().translate(1.0, 2.0, 3.0)
vertices = transform.apply_points(vertices)
```

The delayed form is what products, scenes, planes, bodies, and meshable values
use when they need to store or compose placement before applying it to concrete
arrays.

Internally, `Transform2` stores a homogeneous `3x3` matrix and `Transform3`
stores a homogeneous `4x4` matrix. This is still needed because translation
cannot be represented by a plain `2x2` or `3x3` linear matrix.

Points are converted to homogeneous coordinates, multiplied by `matrix.T`, then
converted back to ordinary point arrays:

$$
[x,\ y] \rightarrow [x,\ y,\ 1]
$$

$$
[x,\ y,\ z] \rightarrow [x,\ y,\ z,\ 1]
$$

Both transform classes expose the same pattern:

| Method | Meaning |
|---|---|
| `Transform2(points=None)` | Create a 2D transform, optionally bound to point data. |
| `Transform3(points=None)` | Create a 3D transform, optionally bound to point data. |
| `.array` | Apply the current transform to the bound points. |
| `with_points(points)` | Attach points to an existing delayed transform. |
| `translate(...)` | Translation. |
| `rotate(...)` | Rotation around a centre or axis. |
| `scale(...)` | Uniform or per-axis scaling about a centre. |
| `mirror(...)` | Reflection across a line in 2D or plane in 3D. |
| `transform(matrix)` | Apply a linear `2x2` or `3x3` matrix. |
| `compose(other)` | Compose two transforms. |
| `inverse()` | Numeric matrix inverse. |
| `apply_points(points)` | Apply to supplied points without rebinding. |

Chained calls are applied in the order they are written. This is why:

```python
Transform2([[1.0, 0.0]]).rotate(pi / 2).translate(1.0, 0.0).array
```

rotates the point first, then translates it.

`Transform3.coerce(value, allow_none=False)` is the only coercion entry point.
It accepts:

- an existing `Transform3`
- any object whose `to_transform3()` returns a `Transform3`
- a 3-number translation tuple
- `None` only when `allow_none=True`, in which case it returns identity

`Transform3.rotate(...)` uses Rodrigues' rotation formula. For unit axis `k` and
relative vector `v = p - o`:

$$
v' =
v\cos\theta
+ (k \times v)\sin\theta
+ k(k\cdot v)(1-\cos\theta)
$$

The final point is `axis_origin + v'`.

Plane-local semantic projection lives on `Plane3`: `coordinates(...)` maps a 3D
point into local `(u, v)`, `signed_distance(...)` measures point offset from the
plane, `project(...)` returns the orthogonal projection, and `fit(...)` builds a
best-fit plane for planar 3D loops. Mesh-only array projection helpers live
inside `operations.meshes` next to the capping and boundary-closing algorithms
that use them.

## Measurement Queries

Distance, intersection, and future area/volume entry points live in
`cady.measurement`. Exact curve length is a `.length` property on geometry
values. See `src/cady/measurement/PLAN.md` for the package plan and current
public surface.

## Polygon Triangulation

`triangulation.py` is a pure-Python fallback triangulator for simple 2D polygon
regions. It is not a full constrained Delaunay triangulator.

`triangulate_float32(vertices, hole_indices=None, dimensions=2)` handles the
simple flat-buffer case by creating a fan:

```text
(0, 1, 2), (0, 2, 3), ..., (0, n-2, n-1)
```

It only supports 2D vertices and rejects `hole_indices` because holes are handled
by `triangulate_polygon(...)`.

`dedupe_closed(points)` removes a repeated final point equal to the first point.

`area2(points)` returns signed ring area using the shoelace formula.

`is_self_intersecting(points)` checks non-adjacent edge pairs using orientation
tests. It skips adjacent edges and the first/last edge pair because they share a
polygon vertex.

### Ear Clipping

`triangulate_polygon(outer, holes=(), tolerance=...)` first deduplicates closing
points and checks the outer loop for self-intersection. Without holes, it calls
`_triangulate_simple_polygon`.

The simple ear-clipping pass:

1. removes repeated consecutive points
2. reverses clockwise rings into counter-clockwise order
3. derives an epsilon from geometry span and tolerance
4. scans vertices for a convex ear
5. rejects ears containing any other polygon vertex
6. emits the triangle and deletes the ear tip
7. removes near-collinear or duplicate vertices if no ear is found
8. raises `WriteError` if it cannot make progress

A candidate ear `(prev, point, next)` is convex when:

$$
\operatorname{cross}(prev, point, next) > \epsilon
$$

and no other remaining point lies inside the candidate triangle.

The geometry epsilon is:

$$
\epsilon =
\max(\text{span}\cdot 10^{-12},\ \text{tolerance}\cdot 10^{-6},\ 10^{-12})
$$

This keeps exact coordinate comparisons from dominating the triangulation of
large or very small shapes.

### Hole Bridging

Polygons with holes are converted into one simple working polygon before ear
clipping.

For each hole:

1. orient the outer boundary counter-clockwise
2. orient holes clockwise
3. choose the hole vertex with maximum `x`, breaking ties toward lower `|y|`
4. sort candidate bridge endpoints on the current polygon
5. keep the first visible bridge
6. splice the hole path into the polygon by duplicating bridge endpoints

A bridge is visible only if samples along the bridge are inside the outer
boundary, outside all holes, and the bridge does not intersect existing polygon
or hole edges except at its own allowed endpoint.

## Mesh Operations

`meshes.py` owns the largest set of algorithms. It works with validated mesh
arrays when operating numerically and returns semantic `Mesh3` values at the
public geometry boundary.

### Mesh Arrays And Boundaries

`coerce_mesh(mesh_or_vertices, faces, edges=None)` returns validated
`(vertices, faces, edges)` arrays:

- vertices: `(n, 3)` float64
- faces: `(m, 3)` int64
- edges: `(k, 2)` int64, empty when omitted

It also accepts an existing tuple of `(vertices, faces)` or
`(vertices, faces, edges)` when `faces` is `None`.

`boundary_edges(mesh)` counts each undirected edge in every triangle. Edges that
appear exactly once are boundary edges.

`stitch_segments(segments)` builds adjacency from undirected boundary segments
and walks unused edges into simple vertex loops. It ignores self-edges and
deduplicates repeated undirected segments.

`boundary_edges_from_faces(faces)` is the tuple-only version of the same
single-use edge count. `prune_dangling_edges(edges)` repeatedly removes vertices
of degree 1 until only cyclic edge structure remains.

`compact_mesh_data(vertices, faces, edges)` removes unused vertices and remaps
face and edge indices into dense index order.

### Cap Triangulation

`triangulate_loop(points, tolerance)` is another ear-clipping loop used for cap
faces. It works in local loop index space and raises `ValueError` if no ear can
be found.

`cap_loops_to_faces(vertices, cap_segments, plane_origin, plane_normal,
tolerance=...)`:

1. stitches cap segments into loops
2. projects each loop into 2D plane coordinates
3. rejects nested loops
4. triangulates each projected loop
5. maps local triangle indices back to original mesh vertex indices

The cap face orientation is reversed as `(loop[a], loop[c], loop[b])` so the cap
normal matches the intended plane side.

`close_planar_cap(...)` caps only boundary edges on a specified plane. With
`snap_tolerance=None`, both edge vertices must already lie on the plane within
`tolerance`. With `snap_tolerance`, near-plane vertices are projected to newly
appended cap vertices while original mesh vertices stay in place.

`close_boundary(...)` closes every planar boundary loop:

1. find boundary edges
2. stitch them into loops
3. fit a best-fit plane to each loop by SVD
4. reject loops whose maximum plane deviation exceeds tolerance
5. project the loop to 2D and triangulate it
6. append cap faces to the mesh

This is only for planar holes. Non-planar hole filling is deliberately not
implemented here.

### Mesh Clipping

`cut_mesh_by_plane(mesh, faces, plane_origin, plane_normal, keep=..., cap=True,
tolerance=...)` clips a triangle mesh against a half-space.

The kept positive side is:

$$
(p-o)\cdot \hat{n} \ge 0
$$

For `keep="negative"`, the normal is negated and the same positive-side logic is
used.

The clipping algorithm:

1. compute signed distances from each triangle vertex to the plane
2. clip each triangle polygon with a Sutherland-Hodgman style half-space pass
3. add or reuse output vertices using a tolerance-rounded spatial key
4. fan-triangulate clipped polygons with more than three vertices
5. skip degenerate triangles whose cross-product area is within `tolerance^2`
6. collect cut-plane segments from clipped polygons
7. optionally cap stitched cut loops

Edge-plane intersections use:

$$
t = \frac{d_0}{d_0-d_1}
$$

and:

$$
p(t)=p_0+t(p_1-p_0)
$$

The vertex dedupe key rounds each coordinate by tolerance:

$$
k(p) =
\left(
\operatorname{round}(x/e),\
\operatorname{round}(y/e),\
\operatorname{round}(z/e)
\right)
$$

### Primitive Triangle Builders

`prism_triangles(origin, size)` returns 12 triangles for an axis-aligned box-like
prism. It creates 8 corners and emits two triangles per rectangular face.

`basis_for_axis(axis, axis_name=None)` creates a local orthonormal basis
`(u, v, w)` where `w` follows the axis. Special axis names `+x`, `-x`, `+y`, and
`-y` force predictable `u,v` choices.

`extrusion_triangles(cap_triangles, loops, hole_flags, offset, axis, axis_name,
distance)`:

1. builds a local basis from the extrusion axis
2. maps 2D cap triangles onto start and end planes
3. reverses start-cap winding and preserves end-cap winding
4. builds two side-wall triangles for each boundary segment
5. flips side-wall winding for hole loops

The 2D-to-3D map is:

$$
P(x,y)=o+xu+yv
$$

`revolution_triangles(profile_points, axis_origin, axis_direction, angle_rad,
tolerance)` builds a coarse surface of revolution around the positive Z axis.
Current limits:

- only `axis_direction == (0, 0, 1)` is supported
- the step count is clamped to at most 160
- rings are connected with two triangles per profile segment per angular step

The angular step count is roughly:

$$
\text{steps} =
\max\left(
12,
\left\lceil
\frac{|\theta|r}{\max(8e,\ 10^{-6})}
\right\rceil
\right)
$$

then clamped to `<= 160`.

`sphere_triangles(centre, radius, tolerance=...)` uses latitude-longitude
tessellation. Rings are:

$$
\text{rings} =
\min\left(64,\ \max\left(8,\ \frac{\text{segments_for_circle}(r,e)}{2}\right)\right)
$$

Segments are `2 * rings`. Points are:

$$
p =
c +
\left(
r\sin\theta\cos\phi,\
r\sin\theta\sin\phi,\
r\cos\theta
\right)
$$

Degenerate pole triangles are skipped.

### Semantic Mesh Constructors

These helpers validate inputs and return `Mesh3`.

`box_mesh(plane, width, depth, height)` builds an oriented box from the plane's
`point(u,v)` mapping and its normal. It returns 8 vertices and 12 faces.

`cylinder_mesh(plane, radius, height, tolerance=...)` chooses the circular
segment count with `segments_for_circle`, builds bottom and top rings, adds two
centre vertices, then emits:

- bottom fan triangles
- top fan triangles
- two side triangles per segment

`sphere_mesh(plane, radius, tolerance=...)` delegates to `sphere_triangles` using
`plane.origin` as the sphere centre, then converts triangles to a `Mesh3`.

`surface_region_mesh(region, surface, tolerance=...)` samples region loops,
triangulates the parameter-space polygon, maps triangle vertices through
`surface.point(u, v)`, and returns a `Mesh3`.

`region_mesh(region, plane, tolerance=...)` wraps the plane as a planar
`Surface3` and delegates to `surface_region_mesh`.

`extrusion_mesh(region, plane, distance, tolerance=...)` triangulates the region
caps, creates an end plane offset by `distance * plane.normal`, then emits cap
triangles and boundary side walls. It rejects zero extrusion distance.

`region_loops_from_region(region, tolerance=...)` extracts region loops either
from `region.loops(tolerance=...)` or from a single `to_array(tolerance=...)`
fallback. All loops must be closed and contain at least three points after
deduping the repeated closing point.

`mesh_from_triangles(triangles)` creates a `Mesh3` by appending three fresh
vertices per triangle. It does not merge shared vertices.

### Loft Operations

`LoftMesh` stores coarse loft results as `vertices`, `faces`, and sampled
`edges`.

`loft_section_polylines(polylines, tolerance=...)` builds a strip mesh across
open section polylines:

1. filter candidate polylines into x-station sections
2. group sections by approximate x coordinate
3. keep the longest candidate in each station bucket
4. orient each section so it rises in z
5. resample every section to a common count
6. connect adjacent rows with quad strips split into two triangles
7. add longitudinal and transverse sample edges

The common sample count is:

$$
\min(\max(\text{section vertex counts}),\ 96)
$$

Resampling uses cumulative polyline arclength and linear interpolation at evenly
spaced arclength values.

Degenerate faces are skipped when any edge length is within tolerance.

### Linesplan Operations

Linesplan helpers normalize, classify, check, and mesh imported wire curves.

Records:

| Record | Meaning |
|---|---|
| `LinesplanCurve` | Normalized source curve with vertices, layer, source index, and entity type. |
| `RejectedLinesplanCurve` | Curve plus rejection reason. |
| `GuideCoverage` | Which section stations a guide curve intersects. |
| `CompatibilityReport` | Counts, guide coverages, and compatibility issues. |
| `LinesplanNetwork` | Sections, buttocks, waterlines, knuckles, rejected curves, report. |

`classify_linesplan_curves(curves, tolerance=...)` accepts either an iterable of
curve-like objects or a `Wireframe3`. Wireframes are split into paths by walking
unambiguous degree-2 runs; branch points split paths.

Classification prefers layer names:

- `SECTION`, `SECTIONS`, `STATION`, `STATIONS`
- `BUTTOCK`, `BUTTOCKS`
- `WATERLINE`, `WATERLINES`
- `KNUCKLE`, `KNUCKLES`

If there is no useful layer, fallback classification uses coordinate span:

- section: x-span <= tolerance
- buttock: y-span <= tolerance
- waterline: z-span <= tolerance

If more than one fallback rule matches, the curve is rejected as ambiguous.

The compatibility report checks whether each guide curve intersects every
section station within tolerance. Missing stations become report issues, and
`is_compatible` is true only when there are no issues.

`mesh_linesplan_network(network, tolerance=..., samples_per_curve=12)` builds a
simple quad-strip mesh:

1. merge section curves with stations within tolerance
2. dedupe section points within tolerance
3. choose y-sample values from uniform samples plus relevant guide points
4. interpolate one point on each section for each y sample
5. connect adjacent station rows with two triangles per grid cell
6. emit section and station grid edges

This is a coarse section-loft mesh, not a fairing or naval-architecture surface
solver.

## Dispatch Operations

`dispatch.py` is the loose, user-facing operation layer. It accepts semantic
objects and routes them to existing methods or local fallback algorithms.

`discretise(target, tolerance=...)`:

1. calls `target.discretise(tolerance=...)` if present
2. otherwise calls `target.to_array(tolerance=...)`
3. converts 2D point arrays to `Polyline2`
4. converts 3D point arrays to `Polyline3`, using `closed=True` when needed

`discretize(...)` is the American spelling alias.

`mesh(target, tolerance=..., surface=None, plane=None, closed=False)`:

1. returns `Mesh2` or `Mesh3` values unchanged
2. maps `mesh(region, surface=...)` through `Region3.from_region(...).to_mesh`
3. maps `mesh(region, plane=...)` through `region_mesh`
4. calls `target.to_mesh(tolerance=...)` if present
5. turns point clouds into vertex-only `Mesh2` or `Mesh3`
6. triangulates `Region2`-like objects with `loops`
7. meshes closed curve-like objects through `to_array`

`triangulate(target, tolerance=..., surface=None, plane=None)`:

1. calls `target.triangulate(tolerance=...)` if present
2. triangulates raw 2D point sequences with `triangulate_polygon`
3. otherwise delegates to `mesh(...)`

This dispatch layer intentionally uses late imports so importing operations does
not eagerly pull in drawing, product, files, or viewer code.

## Lightweight Constructors

`operations.__init__` re-exports operations and also exposes lightweight factory
wrappers. These wrappers late-import semantic classes and return authoring-layer
objects.

| Function | Returns |
|---|---|
| `line2(start, end)` | `Line2` |
| `arc2(centre, radius, start_rad, end_rad)` | `Arc2` |
| `line3(start, end)` | `Line3` |
| `arc3(centre, radius, start_rad, end_rad, x_axis=..., y_axis=...)` | `Arc3` |
| `spline3(control_points)` | `Spline3` |
| `polyline2(vertices, closed=False)` | `Polyline2` |
| `polyline3(items)` | `Polyline3` |
| `circle2(centre, radius)` | `Circle2` |
| `region_rectangle(width, height, origin=...)` | `Region2.rectangle(...)` |
| `region_circle(radius, centre=...)` | `Region2.circle(...)` |
| `box(width, depth, height, plane=None)` | `Body3.box(...)` |
| `cylinder(radius, height, plane=None)` | `Body3.cylinder(...)` |
| `sphere(radius, centre=...)` | `Body3.sphere(...)` |

These are convenience entry points, not numeric algorithms. Their main design
role is to keep top-level imports light while preserving a compact public API.

## Tolerance Rules And Limits

The operations layer uses tolerance in three different ways:

| Use | Examples |
|---|---|
| Sampling density | circle, arc, sphere, Bezier, revolution tessellation |
| Predicate slack | segment hit tests, coplanarity, degeneracy, clipping |
| Deduplication | clipped mesh vertices, section points, cap loops |

This means tolerance is both a geometric accuracy parameter and a robustness
parameter. Very loose values make geometry coarse and merge nearby features.
Very tight values can expose floating-point noise, failed ear clipping, or
non-planar boundary loops.

Current algorithmic limits:

- polygon triangulation is ear clipping, not constrained Delaunay triangulation
- hole support is implemented by visible bridge splicing
- cap triangulation rejects nested loops
- `close_boundary` only closes planar holes
- `revolution_triangles` only supports the positive Z axis
- `mesh_from_triangles` does not merge shared vertices
- linesplan meshing is a coarse section grid, not a fairing solver

The package is therefore best understood as a lightweight geometry operation
layer: explicit, inspectable algorithms with finite tolerance controls, rather
than a general CAD kernel.
