# Polyline To Mesh Spec

**Date:** 2026-06-26
**Status:** implemented

## Problem

Closed 2D polylines currently evaluate to `ArrayPolygon2`, not a triangulated
mesh. The package also has `ArrayPolyline3` and `Wireframe3D` paths, but no
direct closed-polyline-to-mesh API. This makes a common workflow awkward:
turning a closed boundary loop into filled triangle faces.

The target behaviour is:

- a closed 2D polyline can become a 2D triangle mesh object;
- a closed 3D polyline can become a `Mesh3D`;
- open polylines remain curve/wire data and do not silently invent faces.

## Decision

Add an explicit 2D mesh type and closed-polyline meshing methods.

Recommended API shape:

```python
from cady import ClosedPolyline2D, ClosedPolyline3D

mesh2 = ClosedPolyline2D(((0, 0), (1, 0), (1, 1), (0, 1))).to_mesh(tolerance=1e-3)
mesh3 = ClosedPolyline3D(
    ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))
).to_mesh(tolerance=1e-3)
```

For numeric values:

```python
array_mesh2 = mesh2.to_array(tolerance=1e-3)
array_mesh3 = mesh3.to_array(tolerance=1e-3)
```

`Polyline2D` and `Polyline3D` should not expose `to_mesh(...)` unless they are
closed types. If a convenience close operation is added later, it should be
explicit and return a closed type first.

## Data Model

Add `ArrayMesh2` under `cady.operations`, parallel to `ArrayMesh3` but with 2D
vertices:

```python
@dataclass(frozen=True, slots=True)
class ArrayMesh2:
    vertices: PointArray2
    faces: FaceArray
    edges: EdgeArray = ...
```

Add `Mesh2D` under `cady.geometry2d`, parallel to `Mesh3D`:

```python
@dataclass(frozen=True, slots=True)
class Mesh2D:
    vertices: tuple[Vec2, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()
```

`Mesh2D.to_array(tolerance=...)` returns `ArrayMesh2`.

Add `Polyline3D` and `ClosedPolyline3D` only if the API needs a domain-level
3D polyline. They should mirror the 2D split:

- `Polyline3D`: open curve/wire path, no `to_mesh`;
- `ClosedPolyline3D`: planar boundary loop, exposes `to_mesh`.

If the implementation keeps numeric-only 3D polylines for now, then
`ArrayPolyline3.to_mesh(...) -> ArrayMesh3` can be a smaller first step, but the
public top-level API should still prefer domain objects for authoring.

## Meshing Behaviour

2D closed polyline:

- validate positive explicit `tolerance`;
- triangulate the closed ring with `cady.ops.polygons2d.triangulate_polygon`;
- return `Mesh2D` with vertices from the source polyline;
- populate explicit `edges` from the source boundary loop only.

3D closed polyline:

- validate positive explicit `tolerance`;
- fit a best-fit plane to the loop using existing mesh-cut helpers;
- reject non-planar loops when plane deviation exceeds tolerance;
- project to 2D;
- triangulate the projected loop;
- return `Mesh3D` with original 3D vertices and generated faces;
- populate explicit `edges` from the source boundary loop only.

Winding should be stable:

- 2D faces should follow the triangulation orientation.
- 3D faces should be oriented consistently with the fitted plane normal.
- Tests should assert face orientation for a simple world-XY square.

## Non-Goals

- Do not add a third-party triangulation dependency.
- Do not mesh open polylines.
- Do not support holes through `ClosedPolyline2D.to_mesh(...)`; holes remain a
  `Profile2D` concern unless a later API explicitly adds them.
- Do not use `Mesh3D` as the 2D mesh type by stuffing `z=0`; keep 2D and 3D
  data models separate.
- Do not broaden DXF/STL/STEP behaviour in this change.

## Affected Files

Likely implementation files:

- `src/cady/operations/arrays2d.py`
- `src/cady/operations/__init__.py`
- `src/cady/geometry2d/mesh.py`
- `src/cady/geometry2d/curves.py`
- `src/cady/geometry2d/__init__.py`
- `src/cady/geometry3d/curves.py` or `src/cady/operations/arrays3d.py`
- `src/cady/geometry3d/__init__.py`
- `src/cady/__init__.py`
- `tests/operations/test_array_mesh2d.py`
- `tests/geometry2d/test_geometry_mesh2d.py`
- `tests/geometry2d/test_curves.py`
- `tests/geometry3d/test_curves3d.py` or `tests/operations/test_mesh3d.py`
- `tests/conventions/test_import_boundaries.py`
- `tests/conventions/test_stdlib_only.py`
- `tests/test_smoke_import.py`

## Acceptance Criteria

- `ClosedPolyline2D(...).to_mesh(tolerance=...)` returns `Mesh2D`.
- The returned `Mesh2D` has valid vertices, triangular faces, topology edges,
  bounds, and `to_array(...) -> ArrayMesh2`.
- Concave but valid simple closed 2D polylines triangulate correctly.
- Degenerate/self-intersecting 2D loops raise a clear geometry/write error from
  the existing triangulation path.
- A planar closed 3D polyline can become `Mesh3D`.
- A non-planar closed 3D polyline raises a clear `GeometryError`.
- Open polyline types do not grow accidental `to_mesh(...)` support.
- Public exports include the new mesh/polyline types selected by the
  implementation.
- Import boundary and stdlib-only convention tests still pass.

## Risks And Assumptions

- `Mesh2D` is a new public domain type, so export naming and docs should be
  deliberate.
- Existing `triangulate_polygon` is suitable for simple rings and holes; this
  feature should only use the simple-ring path.
- 3D loop triangulation depends on planarity. Non-planar filling is already a
  mesh-hole concern and should not be mixed into closed-polyline authoring.
- If `Polyline3D` is added as a domain type, that is a public API expansion and
  should be tested in smoke imports.

## Verification

Targeted checks:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/operations/test_array_mesh2d.py tests/geometry2d/test_geometry_mesh2d.py tests/geometry2d/test_curves.py
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_curves3d.py tests/operations/test_mesh3d.py
PYTHONPATH=src .venv/bin/pytest -q tests/conventions tests/test_smoke_import.py
```

Final gates:

```bash
PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
git status --short
```
