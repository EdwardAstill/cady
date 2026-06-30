# Cady Operations

The operations package is the numeric layer between semantic CAD values and
array-backed or mesh-backed results. It owns tuple coordinate math, local NumPy
conversion, transforms, triangulation, mesh construction, mesh topology, mesh
clipping, planar closure, primitive triangle generation, lofting, and linesplan
helpers.

The important boundary is:

```text
semantic value -> to_array(tolerance=...) -> operation arrays
semantic value -> to_mesh(tolerance=...)  -> Mesh2 or Mesh3
operation helpers -> tuples, NumPy arrays, or existing semantic mesh values
```

`tolerance` is part of the algorithmic contract. Sampling, meshing,
triangulation, clipping, planar fitting, deduplication, and tolerance-sensitive
predicates take it explicitly instead of hiding a package-wide modelling
resolution.

Sources:

- `src/cady/operations/coordinates.py`
- `src/cady/operations/transforms.py`
- `src/cady/operations/triangulation.py`
- `src/cady/operations/mesh_topology.py`
- `src/cady/operations/mesh_clipping.py`
- `src/cady/operations/meshing.py`
- `src/cady/operations/meshes.py`
- `src/cady/operations/lofting.py`
- `src/cady/operations/__init__.py`

## Package Map

| Module | Role |
|---|---|
| `coordinates` | Pure tuple vector arithmetic in 2D and 3D. |
| `transforms` | Immutable homogeneous affine transform containers for point arrays. |
| `triangulation` | Boundary-guided triangulation of closed 2D loops and planar 3D loops. |
| `mesh_topology` | Boundary edge discovery, loop stitching, dangling-edge pruning, and compaction. |
| `mesh_clipping` | Existing-mesh coercion, plane clipping, explicit planar caps, and planar boundary closure. |
| `meshing` | CAD-facing mesh construction for closed polylines, wireframes, regions, surface regions, and extrusions. |
| `meshes` | Primitive triangle builders, primitive `Mesh3` constructors, tolerance validation, and linesplan helpers. |
| `lofting` | Closed-loop and section-polyline loft helpers. |
| `__init__` | Public re-exports plus lightweight semantic constructors. |

There is no central `operations/arrays.py` module. Geometry values keep tuple
data while being authored, then convert to copied NumPy arrays only at explicit
boundaries such as `to_array(...)`, `to_mesh(...)`, transforms, clipping, and
file/view preparation.

When a module returns arrays, define the narrow type alias in that file, for
example `PointArray3: TypeAlias = NDArray[np.float64]`. Keep validation local
and minimal: public constructors and conversion boundaries should reject obvious
invalid input, but operation code should not be routed through broad validator
helpers just to satisfy type checking.

Bounds, exact curve length, and single-object area/volume properties live with
the semantic object that owns the geometry. Two-geometry queries such as
distance and intersection belong in `cady.measurement`, not `cady.operations`.

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

`is_parallel3(a, b, tolerance=...)` tests whether the cross-product magnitude is
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

## Sampling

Curve sampling lives on the semantic curve objects that own the shape:
`Arc2`, `Arc3`, `Circle2`, `Ellipse2`, `Spline2`, and `Spline3` implement
`to_array(tolerance=...)` directly. `Polyline2` and `Polyline3` store curve
segments and sample them only when `discretise(...)` or `to_array(...)` is
called.

Mesh-specific sampling, such as primitive circle segments, sphere rings,
revolution steps, loop refinement, and section resampling, lives in the
operation module that uses it.

## Transform Operations

`transforms.py` has two public objects: `Transform2` and `Transform3`. Each
object can be used in two ways:

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
stores a homogeneous `4x4` matrix. Translation needs homogeneous coordinates
because it cannot be represented by a plain `2x2` or `3x3` linear matrix.

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
| `to_transform3()` | Return `self` for 3D transform coercion. |

Chained calls are applied in the order they are written:

```python
Transform2([[1.0, 0.0]]).rotate(pi / 2).translate(1.0, 0.0).array
```

rotates the point first, then translates it.

`Transform3.coerce(value, allow_none=False)` accepts:

- an existing `Transform3`
- a `4x4` matrix-like value accepted by `Transform3(matrix=...)`
- any object exposing a usable `matrix`
- any object whose `to_transform3()` returns a `Transform3`-like value
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
best-fit plane for planar 3D loops. Mesh-only projection helpers live near the
capping, clipping, and boundary-closing algorithms that use them.

## Triangulation

`triangulation.py` triangulates closed 2D loops and planar 3D loops. It is a
boundary-guided ear-clipping layer, not a constrained Delaunay triangulator.

Public records and helpers:

| Name | Role |
|---|---|
| `TriangulationGuide` | Optional edge-length constraints for simple boundary refinement. |
| `triangulate_curve2(curve, tolerance=..., guide=None)` | Samples a closed 2D curve and returns `Mesh2`. |
| `triangulate_curve3(curve, tolerance=..., guide=None)` | Samples a closed planar 3D curve and returns `Mesh3`. |
| `triangulate_mesh2(nodes, edges, tolerance=..., guide=None)` | Returns `(nodes, edges, faces)` for closed 2D edge loops. |
| `triangulate_mesh3(nodes, edges, tolerance=..., guide=None)` | Projects planar 3D edge loops and returns `(nodes, edges, faces)`. |
| `triangulate2(...)` | Compatibility wrapper returning `(nodes, faces)` for 2D loops. |
| `triangulate3(...)` | Compatibility wrapper returning `(nodes, faces)` for planar 3D loops. |

`TriangulationGuide.target_edge_length` and `max_edge_length` refine boundary
edges before triangulation. `max_area` and `min_angle_degrees` are accepted by
the record but currently raise `NotImplementedError` when requested.

The 2D ear-clipping pass:

1. stitches input edges into closed loops
2. reverses clockwise loops into counter-clockwise order
3. scans vertices for a convex ear
4. rejects ears containing another loop vertex
5. emits a triangle and deletes the ear tip
6. removes near-collinear vertices if no ear is found
7. stops when only one triangle remains or no progress is possible

A candidate ear `(prev, point, next)` is convex when:

$$
\operatorname{cross}(prev, point, next) > \text{tolerance}
$$

For 3D loops, `triangulate_mesh3(...)` fits a plane by SVD, rejects loops whose
maximum deviation exceeds `tolerance`, projects into local 2D coordinates, then
uses the same loop triangulation.

## Mesh Topology

`mesh_topology.py` contains topology helpers that operate on indexed faces and
edges.

| Function | Meaning |
|---|---|
| `boundary_edges(mesh)` | Count triangle edges and return those used by exactly one face. |
| `boundary_edges_from_faces(faces)` | Tuple-oriented boundary edge helper for semantic meshes. |
| `stitch_segments(segments)` | Walk undirected segments into simple vertex loops. |
| `edge_loops(edges)` | Validate edge arrays and return closed loops. |
| `prune_dangling_edges(edges)` | Repeatedly remove degree-1 branches until only cycles remain. |
| `compact_mesh_data(vertices, faces, edges)` | Drop unused vertices and remap indices densely. |

These helpers know topology, not CAD semantics. They do not import drawing,
product, files, or viewer code.

## Mesh Clipping And Closure

`mesh_clipping.py` owns operations on existing triangle mesh arrays.

`coerce_mesh(mesh_or_vertices, faces, edges=None)` returns validated
`(vertices, faces, edges)` arrays:

- vertices: `(n, 3)` float64
- faces: `(m, 3)` int64
- edges: `(k, 2)` int64, empty when omitted

It also accepts an existing tuple of `(vertices, faces)` or
`(vertices, faces, edges)` when `faces` is `None`.

`close_planar_cap(...)` caps boundary edges on an explicit plane. With
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

## CAD-Facing Meshing

`meshing.py` turns semantic boundaries into semantic mesh values.

| Function | Meaning |
|---|---|
| `closed_polyline_mesh2(polyline, tolerance=..., guide=None)` | Fill a closed 2D polyline with `Mesh2`. |
| `closed_polyline_mesh3(polyline, tolerance=..., guide=None)` | Fill a closed planar 3D polyline with `Mesh3`. |
| `wireframe_mesh(wireframe, tolerance=..., guide=None)` | Triangulate closed planar wireframe edge loops into `Mesh3`. |
| `region_mesh(region, plane, tolerance=..., guide=None)` | Place a parameter region on a plane and mesh it. |
| `surface_region_mesh(region, surface, tolerance=..., guide=None)` | Mesh a bounded region on a `Surface3`. |
| `extrusion_mesh(region, plane, distance=..., tolerance=..., guide=None)` | Extrude a 2D region along a plane normal. |
| `region_loops_from_region(region, tolerance=...)` | Extract labelled outer and hole loops from a region-like value. |
| `triangulate_polygon(outer, holes=(), tolerance=...)` | Ear-clip a 2D polygon, bridging holes first. |
| `mesh_from_triangles(triangles)` | Build a `Mesh3` with fresh vertices for each triangle. |

Region meshing supports `guide=None`; guide constraints are currently rejected
for region and extrusion meshing because the guide is not applied to generated
region interiors.

### Polygon Triangulation With Holes

`triangulate_polygon(outer, holes=(), tolerance=...)` deduplicates repeated
closing points and triangulates the polygon. Without holes, it calls the simple
ear-clipping path. With holes, it first splices holes into the outer polygon.

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

`extrusion_mesh(...)` triangulates the start and end caps, offsets the end plane
by `distance * plane.normal`, and emits two side-wall triangles for each outer
and hole boundary segment. It rejects zero extrusion distance.

## Primitive Mesh Helpers

`meshes.py` contains primitive triangle builders and semantic `Mesh3`
constructors.

`segments_for_circle(radius, tolerance)` estimates a circle segment count from
the supplied tolerance and enforces a practical lower bound.

`prism_triangles(origin, size)` returns 12 triangles for an axis-aligned
box-like prism. It creates 8 corners and emits two triangles per rectangular
face.

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

`sphere_triangles(centre, radius, tolerance=...)` uses latitude-longitude
tessellation. Degenerate pole triangles are skipped.

Semantic constructors validate inputs and return `Mesh3`:

| Function | Meaning |
|---|---|
| `box_mesh(plane, width=..., depth=..., height=...)` | Oriented box from a `Plane3`. |
| `cylinder_mesh(plane, radius=..., height=..., tolerance=...)` | Ring-based cylinder mesh. |
| `sphere_mesh(plane, radius=..., tolerance=...)` | Sphere centred at `plane.origin`. |

`validate_tolerance(...)` and `validate_positive(...)` are small local helpers
used by primitive meshing code.

## Loft Operations

`lofting.py` stores coarse loft results in:

| Record | Meaning |
|---|---|
| `LoftMesh` | Vertices, faces, and sampled edges from a loft operation. |

`loft_closed_curves3(start_curve, end_curve, tolerance=..., guide=None)` samples
two closed 3D curves and delegates to `loft_closed_loops3(...)`.

`loft_closed_loops3(start, end, tolerance=..., guide=None)` resamples two closed
loops to a shared count, connects corresponding vertices with quad strips split
into triangles, and returns a `Mesh3`. Guide constraints are currently rejected
for lofting because they are not applied to generated interior faces.

`loft_section_polylines(polylines, tolerance=...)` builds a coarse strip mesh
across open section polylines:

1. group candidate sections by approximate x coordinate
2. keep the longest candidate in each station bucket
3. orient each section so it rises in z
4. resample every section to a common count
5. connect adjacent rows with quad strips split into two triangles
6. add longitudinal and transverse sample edges

The common sample count is:

$$
\min(\max(\text{section vertex counts}),\ 96)
$$

Resampling uses cumulative polyline arclength and linear interpolation at evenly
spaced arclength values. Degenerate faces are skipped when any edge length is
within tolerance.

## Linesplan Operations

Linesplan helpers normalize, classify, check, and mesh imported wire curves.
They currently live in `meshes.py`.

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

## Lightweight Constructors And Public Exports

`operations.__init__` re-exports the compact public operations surface:

- `Transform2`, `Transform3`
- `TriangulationGuide`
- `triangulate2`, `triangulate3`
- `triangulate_curve2`, `triangulate_curve3`
- `triangulate_mesh2`, `triangulate_mesh3`
- `close_boundary`, `close_planar_cap`, `cut_mesh_by_plane`
- `sphere_triangles`

It also exposes lightweight factory wrappers. These wrappers late-import
semantic classes and return authoring-layer objects.

| Function | Returns |
|---|---|
| `line2(start, end)` | `Line2` |
| `arc2(centre, radius, start_rad, end_rad)` | `Arc2` |
| `line3(start, end)` | `Line3` |
| `arc3(centre, radius, start_rad, end_rad, x_axis=..., y_axis=...)` | `Arc3` |
| `spline3(control_points)` | `Spline3` |
| `polyline2(vertices, closed=False)` | `Polyline2` |
| `polyline3(items, closed=False)` | `Polyline3` |
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
| Sampling density | circle, arc, sphere, Bezier, revolution tessellation, loft resampling |
| Predicate slack | segment hit tests, coplanarity, degeneracy, clipping |
| Deduplication | clipped mesh vertices, section points, cap loops, refined edges |

This means tolerance is both a geometric accuracy parameter and a robustness
parameter. Very loose values make geometry coarse and merge nearby features.
Very tight values can expose floating-point noise, failed ear clipping, or
non-planar boundary loops.

Current algorithmic limits:

- triangulation is ear clipping, not constrained Delaunay triangulation
- hole support in region meshing is implemented by visible bridge splicing
- cap triangulation rejects nested loops
- `close_boundary` only closes planar holes
- `close_holes` is not implemented on `Mesh3`
- `revolution_triangles` only supports the positive Z axis
- `mesh_from_triangles` does not merge shared vertices
- `TriangulationGuide.max_area` and `min_angle_degrees` are not implemented
- region meshing and lofting reject unapplied guide constraints
- linesplan meshing is a coarse section grid, not a fairing solver

The package is therefore best understood as a lightweight geometry operation
layer: explicit, inspectable algorithms with finite tolerance controls, rather
than a general CAD kernel.
