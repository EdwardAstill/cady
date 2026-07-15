# Point Clouds

Point clouds are unconnected point collections. Use them when the data has
sample locations or node positions but no curve, mesh, face, or edge topology.

## `PointCloud2`

`PointCloud2` stores unconnected `Point2` values. Coordinate sequences passed
to the constructor are normalized to those immutable point values.

```python
from cady import PointCloud2
from cady.operations.transforms import Transform2

cloud = PointCloud2([(0.0, 0.0), (1.0, -2.0)])
lower, upper = cloud.bounds()
array = cloud.to_array(tolerance=1e-3)
move = Transform2(cloud.vertices).translate(0.0, 2.0)
moved = cloud.transformed(move)
```

- Constructor input is an iterable of 2D coordinate sequences.
- `vertices` and `points()` return the stored `Point2` values.
- `bounds()` returns `(lower, upper)` as `Point2` values and raises for an empty
  cloud.
- `to_array(tolerance=...)` returns an `(n, 2)` NumPy array and validates that
  tolerance is positive.
- `transformed(transform)` accepts `Transform2`.
- `mirror(point, direction)` mirrors around a 2D axis.

## `PointCloud3`

`PointCloud3` is the equivalent collection of `Point3` values.

```python
from cady import PointCloud3
from cady.operations.transforms import Transform3

cloud = PointCloud3([(0.0, 0.0, 0.0), (1.0, -2.0, 3.0)])
lower, upper = cloud.bounds()
array = cloud.to_array(tolerance=1e-3)
moved = cloud.transformed(Transform3().translate(0.0, 0.0, 2.0))
```

- Constructor input is an iterable of 3D coordinate sequences.
- `vertices` and `points()` return the stored `Point3` values.
- `bounds()` returns `(lower, upper)` as `Point3` values and raises for an empty
  cloud.
- `to_array(tolerance=...)` returns an `(n, 3)` NumPy array and validates that
  tolerance is positive.
- `transformed(transform)` accepts `Transform3`.
- `mirror(plane_origin, plane_normal)` mirrors across a 3D plane.
- `view(...)` opens a point-rendered 3D view when the optional view extras are
  installed.
