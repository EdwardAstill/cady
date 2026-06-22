# Array Operations

`cady.ops` is the object-agnostic algorithm layer. Functions in this layer work
with primitive values: NumPy arrays, array-like lists or tuples, and plain
scalars. They may use NumPy internally for vectorised calculation, but they do
not import or inspect `cady.domain` objects.

The boundary is deliberate:

```text
domain object.to_array(...) -> ops primitive function -> numeric result
```

Domain objects preserve CAD intent. Ops functions perform reusable numeric
work. Numeric objects hold validated arrays.

## Accepted Inputs

Ops functions should accept values such as:

- point arrays with shape `(n, 2)` or `(n, 3)`;
- single points as tuples or arrays;
- face arrays with shape `(m, 3)`;
- scalar radii, distances, angles, and tolerances;
- primitive axis origins and directions.

They should not accept `Circle`, `Rectangle`, `Extrusion`, `Model`, or other
domain objects as core arguments.

## Domain Adaptation

Domain `to_array(...)` methods unpack object attributes before calling ops:

```python
class Circle:
    def to_array(self, *, tolerance: float):
        from cady.numeric import ArrayPolyline2
        from cady.ops.curves2d import sample_circle_points

        vertices = sample_circle_points(
            (self.centre.x, self.centre.y),
            self.radius,
            tolerance,
        )
        return ArrayPolyline2(vertices, closed=True)
```

The ops function does not know that the centre and radius came from a
`Circle`. The same function can be reused by file readers, generated arrays, user
code, or tests.

## Curve Sampling

Curve operations cover primitive sampling and evaluation:

- `sample_circle_points(centre, radius, tolerance)`
- `sample_arc_points(centre, radius, start_rad, end_rad, tolerance)`
- `sample_bezier_points(control_points, tolerance)`
- `evaluate_bezier_spline2(spline_or_control_points, t_values)`

Tolerance is a geometric error budget. Smaller tolerances produce more sample
points; larger tolerances produce fewer points. Sampling is explicit, so an
analytic spline can be carried as control points until a caller asks for
vertices.

## Polygon Operations

Polygon operations work over arrays rather than shape objects:

- area and signed area;
- centroid;
- bounds;
- closed-loop handling;
- holes;
- triangulation preparation.

Closed profiles should use one outer loop and zero or more hole loops. The
operation layer should not infer hole semantics from domain state; callers pass
the primitive outer and hole arrays directly.

## Meshing Operations

Meshing functions produce numeric meshes from primitive geometry:

- `mesh_prism(origin, size)`
- `mesh_extrusion(outer, holes, axis, distance)`
- `mesh_revolution(profile_points, axis_origin, axis_direction, angle_rad, tolerance)`
- `mesh_sphere(centre, radius, tolerance)`
- `cut_mesh_by_plane(mesh, plane_origin, plane_normal, keep="positive", cap=True)`

These functions return `ArrayMesh3` or the primitive arrays used to construct
one. They should be usable without importing `cady.domain`.

`cut_mesh_by_plane(...)` clips an evaluated triangle mesh to one half-space.
The positive side is where `dot(point - plane_origin, plane_normal) >= 0`.
Use `keep="negative"` for the opposite side. With `cap=True`, cady fills simple
non-nested cut loops so the result remains closed; use `cap=False` when you
only need an open sectioned mesh.

## Transform Conventions

Bulk transforms operate on `(n, 2)` or `(n, 3)` arrays. The fast path uses
row-vector arrays:

```python
points_global = points_local @ rotation.T + translation
```

`Transform2.apply_points(...)`, `Transform3.apply_points(...)`, and
`Pose3.apply_points(...)` should preserve input shape, return finite
`float64` arrays, and leave face arrays unchanged when transforming meshes.

## Compatibility

Existing tuple-based tessellation helpers can remain as compatibility surfaces
while file writers migrate. Core `ops` functions should move toward primitive
array/list/scalar signatures. Compatibility adapters can sit outside core ops
or behind domain `to_array(...)` methods.
