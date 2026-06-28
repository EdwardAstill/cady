# Geometry Operation Notes

This note captures the current direction for shared geometry behavior in `cady`.
The implementation should keep semantic values immutable and push reusable
numeric algorithms into `cady.operations` only when they apply across multiple
geometry types.

## Object-Level Shape

Common authoring values should expose these concepts where they make sense:

- `bounds()` returns the value's extents as `(min_point, max_point)`.
- `points()` returns representative semantic points.
- `boundary` is an attribute returning the same min/max corner pair as `bounds()`.
- `to_array(tolerance=...)` converts to the explicit numeric representation.
- `discretise(tolerance=...)` converts curved geometry to straight segments.
- `to_mesh(tolerance=...)` converts meshable geometry to a mesh.
- `to_wireframe()` and other `to_*()` methods convert between semantic values.
- `transformed(transform)` returns a new transformed value.
- `rotate(...)` is a convenience transformation: around a point for 2D, around an axis for 3D.
- `mirror(...)` is a convenience transformation: about a line for 2D, about a plane for 3D.

`to_array(tolerance=...)` may call `discretise(tolerance=...)` internally when
the value has not already been discretised. Sampling tolerances stay explicit.

## Placement And Projection

- `project_*` helpers belong in `operations.projections` when they are reused by
  several values or mesh algorithms.
- `to_2d(...)` should mean "project a 3D value onto a plane"; the default plane
  is world XY.
- `place_3d(...)` should mean "place a 2D value on a 3D plane", with explicit
  origin, x-axis, and y-axis/normal behavior.
- Projection onto non-planar surfaces should stay operation-level until there is
  a concrete semantic object that needs it.

## Operation Modules

- `operations.dispatch` owns generic `discretise`, `mesh`, and `triangulate`
  dispatch.
- `operations.projections` owns plane fitting and projection helpers.
- `operations.intersections` owns line/plane/surface intersection helpers.
- `operations.distances` owns point, line, and plane distance helpers.
- `operations.transforms` owns point-level and affine transformations.
- `operations.meshes` owns mesh generation and mesh topology algorithms.
- `operations.triangulation` owns polygon triangulation.
- `operations.sampling` owns curve discretisation helpers.
- Mesh operation boundaries use plain `(vertices, faces, edges)` NumPy array
  tuples; there is no array-mesh object.

Keep operations reusable and import-light: operations must not import drawing,
product, view, or file facade modules.

## Current Implementation Status

- Implemented: generic `discretise`, `mesh`, and `triangulate` dispatch.
- Implemented: shared projections, intersections, distances, transforms,
  sampling, mesh generation, and triangulation modules.
- Implemented: finite 2D and 3D geometry values expose `boundary` as their
  bounding min/max corner pair.
- Implemented: mesh topology remains explicit as `boundary_loops`; `boundary`
  is not used for open mesh edge loops.
- Implemented: removed the `ArrayMesh3` wrapper; array mesh data is represented
  only as `(vertices, faces, edges)` arrays.

## Still To Normalize

- Add convenience `rotate(...)` methods consistently where the local value type
  already supports `transformed(...)`.
- Add `discretise(...)` methods to 2D curve classes that currently only expose
  `to_array(tolerance=...)`.
- Decide exact names and signatures for `to_2d(...)` and `place_3d(...)` before
  adding public API.
- Keep direct methods on semantic objects when the behavior is object-specific;
  move behavior into operations only when it is useful across different objects.
