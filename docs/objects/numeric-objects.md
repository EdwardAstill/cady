# Numeric Objects

Numeric objects are the NumPy-backed evaluated geometry layer. They are built
for fast calculations, matrix transforms, meshing, plotting, and viewer
conversion. They sit beside the semantic domain model rather than replacing it.

All numeric arrays are expected to be finite and validated. Point arrays use
`float64`; face arrays use `int64`.

## 2D Geometry

`ArrayPolyline2`

- `vertices`: float array with shape `(n, 2)`
- `closed`: `bool`
- represents sampled or user-supplied 2D vertices

`ArrayPolygon2`

- `outer`: float array with shape `(n, 2)`
- `holes`: tuple of float arrays, each with shape `(m, 2)`
- represents filled profiles, including holes

`ArrayBezierSpline2`

- `control_points`: float array with shape `(3n + 1, 2)`
- `closed`: `bool`
- represents cubic Bezier control points analytically

`ArrayBezierSpline2` is not a polyline. It is sampled only when a caller asks
for points through a sampling function, tessellation, export, or
visualisation.

## 3D Geometry

`ArrayPolyline3`

- `vertices`: float array with shape `(n, 3)`
- represents 3D vertex chains and wire geometry

`ArrayMesh3`

- `vertices`: float array with shape `(n, 3)`
- `faces`: integer array with shape `(m, 3)`
- `triangles`: derived float array with shape `(m, 3, 3)`

`ArrayMesh3` is the central fast representation for STL output, static 3D
plotting, interactive viewers, mesh bounds, volume calculations, and bulk
rotation or translation. Faces index into the vertex array, so transforms can
update vertices while leaving topology unchanged.

`EvaluatedSolid3`

- `source`: the semantic `Shape3D` that produced the mesh
- `mesh`: `ArrayMesh3`
- `tolerance`: the tolerance used during evaluation

Use this wrapper when callers need to keep provenance and tolerance metadata
with an evaluated mesh.

## Transforms

`Transform2`

- stores a `(3, 3)` homogeneous matrix;
- supports identity, translation, rotation, scale, mirror/reflection,
  composition, inverse, and `apply_points(points)`.

`Transform3`

- stores a `(4, 4)` homogeneous matrix;
- supports identity, translation, arbitrary-axis rotation, scale,
  mirror/reflection, composition, inverse, and `apply_points(points)`.

`Pose3`

- stores a local-to-global `(3, 3)` rotation and `(3,)` translation;
- converts to `Transform3`;
- applies the fast row-vector transform directly.

The fast path uses row-vector arrays:

```python
vertices_global = vertices_local @ rotation.T + translation
```

Example mesh rotation:

```python
from cady import rectangle
from cady.numeric import Transform3

profile = rectangle((0, 0), (1.0, 0.6))
mesh = profile.extrude("+z", 0.04).to_array(tolerance=1e-3)

turn = Transform3.rotation((0, 0, 0), (0, 0, 1), 1.5707963267948966)
rotated = mesh.transformed(turn)
```

Example mesh merging:

```python
from cady.numeric import ArrayMesh3

combined = ArrayMesh3.merged([plate_mesh, pin_mesh])
```

Merging offsets face indices so each source mesh keeps valid topology in the
combined vertex array.

## Validation Rules

The validation helpers coerce array-like inputs into canonical arrays and
reject invalid geometry early:

- `as_points2(value)` returns a finite `float64` array with shape `(n, 2)`;
- `as_points3(value)` returns a finite `float64` array with shape `(n, 3)`;
- `as_faces(value)` returns an `int64` array with shape `(m, 3)`;
- `as_matrix3(value)` returns a finite `float64` array with shape `(3, 3)`;
- `as_matrix4(value)` returns a finite `float64` array with shape `(4, 4)`.

Wrong rank, wrong trailing dimension, `NaN`, and infinite values should raise
validation errors instead of producing malformed geometry later.
