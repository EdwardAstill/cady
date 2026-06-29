# Cady Operations

The operations package is the numeric layer between semantic CAD values and
meshable or array-backed results. It owns tuple coordinate math, NumPy validation,
sampling, transforms, projections, distances, intersections, polygon
triangulation, mesh construction, mesh clipping, capping, lofting, and smart
dispatch.

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
- `src/cady/operations/arrays.py`
- `src/cady/operations/sampling.py`
- `src/cady/operations/transforms.py`
- `src/cady/operations/projections.py`
- `src/cady/operations/distances.py`
- `src/cady/operations/intersections.py`
- `src/cady/operations/triangulation.py`
- `src/cady/operations/meshes.py`
- `src/cady/operations/dispatch.py`
- `src/cady/operations/__init__.py`

## Package Map

| Module | Role |
|---|---|
| `coordinates` | Pure tuple vector arithmetic in 2D and 3D. |
| `arrays` | NumPy array validation, bounds, Bezier sampling, and polyline measurements. |
| `sampling` | Analytic 2D curve sampling for circles, arcs, cubic Beziers, and offsets. |
| `transforms` | Point transforms plus immutable homogeneous affine transform containers. |
| `projections` | Plane fitting, plane bases, and projection into plane-local coordinates. |
| `distances` | Distances and closest points for points, bounded segments, and planes. |
| `intersections` | Segment/segment, segment/plane, plane/plane, and planar surface intersections. |
| `triangulation` | Pure-Python polygon triangulation with ear clipping and hole bridging. |
| `meshes` | Mesh coercion, boundaries, caps, clipping, primitives, extrusion, lofts, linesplans. |
| `dispatch` | User-facing operation dispatch for `discretise`, `mesh`, and `triangulate`. |
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

## Array Validation And Measurements

`arrays.py` converts arbitrary point-like input into copied, finite NumPy arrays.
The copy matters: callers cannot mutate the original input and accidentally
change the operation result.

| Helper | Accepted shape | Result |
|---|---:|---|
| `as_points2` | `(n, 2)` finite numeric | `float64` point array |
| `as_points3` | `(n, 3)` finite numeric | `float64` point array |

`bounds2(points)` and `bounds3(points)` compute axis-aligned bounding corners:

$$
\min(P) = \left(\min_i x_i,\ \min_i y_i,\ \min_i z_i\right)
$$

$$
\max(P) = \left(\max_i x_i,\ \max_i y_i,\ \max_i z_i\right)
$$

The 2D version uses only `x,y`. Empty point arrays are rejected because bounds
are undefined without at least one point.

### Polygon Area And Centroid

`polyline2_area(vertices)` uses the shoelace formula on a closed ring. If the
first point is repeated as the last point, the duplicate closing point is removed
first.

$$
A_s =
\frac{1}{2}
\sum_i
\left(x_i y_{i+1} - x_{i+1} y_i\right)
$$

The public area is `abs(A_s)`. The sign is still useful internally because it
encodes winding direction.

`polyline2_centroid(vertices)` uses the standard polygon centroid:

$$
C_x =
\frac{1}{6A_s}
\sum_i
(x_i+x_{i+1})(x_i y_{i+1}-x_{i+1}y_i)
$$

$$
C_y =
\frac{1}{6A_s}
\sum_i
(y_i+y_{i+1})(x_i y_{i+1}-x_{i+1}y_i)
$$

If the signed area is exactly zero, the centroid falls back to the arithmetic
mean of the points. This handles degenerate rings without dividing by zero.

`polyline2_length(vertices, closed=False)` sums Euclidean segment lengths. When
`closed=True`, it adds the final segment from the last vertex back to the first
vertex.

### Array Bezier Spline

`ArrayBezierSpline2` stores piecewise cubic Bezier control points as a validated
`(n, 2)` array. The control-point count must be `3k + 1`, where `k >= 1`.

Each segment uses four control points:

$$
B(t) =
(1-t)^3P_0
+ 3(1-t)^2tP_1
+ 3(1-t)t^2P_2
+ t^3P_3
,\quad 0 \le t \le 1
$$

`evaluate_bezier_spline2(spline, t_values)` treats `t_values` as normalized
parameters across the whole spline. For `segment_count = k`, it scales each
global parameter by `k`, floors it to choose the segment, then evaluates the
local cubic.

`sample_bezier_spline2(...)` samples the spline either by explicit `samples` or
by a tolerance-derived density:

$$
\text{samples_per_segment} =
\max\left(4,\ \left\lceil\frac{1}{\sqrt{\text{tolerance}}}\right\rceil\right)
$$

If neither `samples` nor `tolerance` is supplied, it uses 16 samples per segment.
Closed splines append the first vertex if the sampled final vertex does not
already match it.

`polyline3_transformed(vertices, transform)` validates 3D vertices and delegates
the numeric mapping to any object with `apply_points(points)`.

## Sampling Operations

`sampling.py` turns analytic 2D curves into point sequences. The key control is
the circle chord error.

For a circle of radius `r` and sagitta tolerance `e`, the half-angle satisfies:

$$
e = r(1-\cos(\alpha))
$$

So the full segment angle is:

$$
\Delta\theta =
2\arccos\left(1-\frac{e}{r}\right)
$$

`segments_for_circle(radius, tolerance)` returns:

$$
n =
\max\left(12,\ \left\lceil \frac{2\pi}{\Delta\theta} \right\rceil\right)
$$

If `tolerance >= radius`, it returns the minimum 12 segments. Tolerance is
clamped internally to at least `1e-9` for this calculation.

`circle_points(centre, radius, tolerance=...)` samples:

$$
p_i =
\left(
c_x + r\cos\frac{2\pi i}{n},\
c_y + r\sin\frac{2\pi i}{n}
\right)
$$

for `i = 0 ... n-1`.

`arc_points(centre, radius, start_rad, end_rad, tolerance=...)` samples both
endpoints. It scales the full-circle segment count by the absolute sweep angle:

$$
n =
\max\left(
2,
\left\lceil
\frac{|\theta_1-\theta_0|}{2\pi}
\text{segments_for_circle}(r,e)
\right\rceil
\right)
$$

`cubic_bezier_points(control_points, tolerance=...)` samples chained cubic
Bezier segments with:

$$
\text{samples} =
\max\left(8,\ \left\lceil\frac{1}{\sqrt{\text{tolerance}}}\right\rceil\right)
$$

It skips the first point of later segments so shared segment endpoints do not
appear twice.

`midpoint(a, b)` returns `(a+b)/2`.

`perpendicular(vector)` normalizes the input and returns the left-hand
perpendicular:

$$
\operatorname{perp}(x,y) = (-y,\ x)
$$

`offset_point(point, direction, distance)` moves the point along that unit
perpendicular:

$$
p' = p + d\operatorname{perp}(\hat{v})
$$

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

## Plane Projection Operations

`projections.py` is used by mesh capping and clipping when 3D loops need a 2D
working plane.

`vector3(value, name=...)` validates one finite 3D vector. `unit3(...)` also
normalizes it.

`basis_for_plane(normal)` builds an orthonormal basis `(u, v)` in a plane:

1. choose a reference axis that is not nearly parallel to the normal
2. compute `u = normal x reference`
3. normalize `u`
4. compute `v = normal x u`

This gives two perpendicular in-plane axes.

`project_loop(loop, vertices, origin, normal)` maps vertex indices into 2D
plane coordinates:

$$
(u_i, v_i) =
\left(
(p_i-o)\cdot \hat{u},\
(p_i-o)\cdot \hat{v}
\right)
$$

`fit_plane_svd(points)` fits a best-fit plane:

1. compute the centroid
2. subtract it from the points
3. run SVD on the centered points
4. take the last right-singular vector as the plane normal
5. flip the normal toward positive global Z when needed

The last singular vector is the direction of least variance, so it is the normal
of the best-fit plane in a least-squares sense.

`max_plane_deviation(points, origin, normal)` returns:

$$
\max_i |(p_i-o)\cdot n|
$$

`project_point_to_plane(point, distance, normal)` subtracts the signed normal
offset:

$$
p' = p - d n
$$

## Distance And Closest-Point Operations

`distances.py` supports point/point, point/plane, line/line, and line/plane
distances. Line-like inputs are treated as bounded segments.

Result records:

| Record | Meaning |
|---|---|
| `ClosestPoints2` | Distance, closest 2D endpoints, and both segment parameters. |
| `ClosestPoints3` | Distance, closest 3D endpoints, and both segment parameters. |
| `LinePlaneClosestPoint` | Minimum line-plane distance, closest point, segment parameter. |

`distance(left, right, tolerance=...)` dispatches by shape and attributes:

- point-like sequences of length 2 or 3
- line-like objects with `start` and `end`, or a pair of point-like values
- plane-like objects with `origin` and `normal`

`signed_distance_to_plane(point, origin, normal)` computes:

$$
d_s = (p-o)\cdot \hat{n}
$$

The public point-plane distance uses `abs(d_s)`.

`closest_line_plane(line, origin, normal)` evaluates the signed distances at
both segment endpoints:

- if either endpoint is on the plane, that endpoint is the closest point
- if the signs differ, the segment crosses the plane and the distance is zero
- otherwise the closer endpoint is returned

For a crossing segment, the intersection parameter is:

$$
t = \frac{d_0}{d_0-d_1}
$$

and the point is linearly interpolated:

$$
p(t)=p_0+t(p_1-p_0)
$$

`closest_points_between_segments3(left, right, tolerance=...)` is the bounded
segment closest-point algorithm. With:

$$
d_1=q_1-p_1,\quad d_2=q_2-p_2,\quad r=p_1-p_2
$$

and scalar terms:

$$
a=d_1\cdot d_1,\quad e=d_2\cdot d_2,\quad f=d_2\cdot r
$$

it solves for segment parameters `s,t` in `[0,1]`. Degenerate segments collapse
to endpoint cases when their squared length is within `tolerance^2`.

For non-degenerate segments it uses:

$$
b=d_1\cdot d_2,\quad c=d_1\cdot r,\quad D=ae-b^2
$$

$$
s = \frac{bf-ce}{D}
$$

then clamps `s` and `t` to the bounded segment interval. Parallel segments use
`s = 0` as the initial fallback before endpoint correction.

`closest_points_between_segments2(...)` lifts 2D segments into `z=0`, runs the
3D algorithm, then drops the `z` coordinate.

## Intersection Operations

`intersections.py` returns unique intersections for supported pairs and `None`
when there is no unique hit.

Result records:

| Record | Meaning |
|---|---|
| `LineIntersection2` | Point plus both segment parameters. |
| `LineIntersection3` | Point plus both segment parameters. |
| `LinePlaneIntersection` | Point plus line parameter. |
| `InfiniteLine3` | Plane-plane intersection line as point plus direction. |

`intersect(left, right, tolerance=...)` dispatches:

- planar `Surface3` against planar `Surface3`
- plane against plane
- line segment against line segment
- line segment against plane

Planar surfaces are recognized by `kind == "plane"` and `base_plane`.

### 2D Segment Intersection

For two bounded 2D segments:

$$
p + tr = q + us
$$

where `r = p_end - p` and `s = q_end - q`.

The denominator is the 2D cross product:

$$
D = r \times s
$$

If `|D| <= tolerance`, the segments are parallel or collinear and the helper
returns `None`. Otherwise:

$$
t = \frac{(q-p)\times s}{D}
$$

$$
u = \frac{(q-p)\times r}{D}
$$

The result is accepted only if both parameters lie in `[0,1]` within tolerance.

### 3D Segment Intersection

`line3_line3_intersection(...)` delegates to
`closest_points_between_segments3(...)`. If the closest-point distance is within
tolerance, the returned intersection point is the midpoint of the two closest
points.

This makes skew lines return `None`, while nearly coincident bounded hits are
accepted according to the supplied tolerance.

### Line-Plane Intersection

For segment `p0 -> p1`, direction `d = p1-p0`, plane origin `o`, and normal `n`:

$$
t = \frac{n\cdot(o-p_0)}{n\cdot d}
$$

If the denominator is near zero, the line is parallel to the plane and returns
`None`. If `bounded=True`, `t` must lie in `[0,1]` within tolerance.

### Plane-Plane Intersection

Two planes intersect in an infinite line unless their normals are parallel.

The direction is:

$$
d = \hat{n}_1 \times \hat{n}_2
$$

If `||d||^2 <= tolerance^2`, the planes are treated as parallel and the helper
returns `None`.

For planes in Hessian-style form:

$$
\hat{n}_1\cdot x = d_1,\quad \hat{n}_2\cdot x = d_2
$$

the implementation computes one point on the intersection line as:

$$
p =
\frac{
\left(d_1\hat{n}_2 - d_2\hat{n}_1\right)\times d
}{
d\cdot d
}
$$

The returned direction is normalized.

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
