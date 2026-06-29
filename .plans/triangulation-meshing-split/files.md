# File Map

## src/cady/operations/triangulation.py

Primary API:

```python
@dataclass(frozen=True, slots=True)
class TriangulationGuide:
    target_edge_length: float | None = None
    max_edge_length: float | None = None
    max_area: float | None = None
    min_angle_degrees: float | None = None

def triangulate_curve2(curve: object, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh2: ...
def triangulate_curve3(curve: object, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...

def triangulate_mesh2(nodes: object, edges: object, *, tolerance: float = 1e-9, guide: TriangulationGuide | None = None) -> tuple[PointArray2, EdgeArray, FaceArray]: ...
def triangulate_mesh3(nodes: object, edges: object, *, tolerance: float = 1e-9, guide: TriangulationGuide | None = None) -> tuple[PointArray3, EdgeArray, FaceArray]: ...

def triangulate2(nodes: object, edges: object, *, tolerance: float = 1e-9, guide: TriangulationGuide | None = None) -> tuple[PointArray2, FaceArray]: ...
def triangulate3(nodes: object, edges: object, *, tolerance: float = 1e-9, guide: TriangulationGuide | None = None) -> tuple[PointArray3, FaceArray]: ...
```

Important private helpers:

```python
def _coerce_points2(value: object) -> PointArray2: ...
def _coerce_points3(value: object) -> PointArray3: ...
def _coerce_edges(value: object) -> EdgeArray: ...
def _validate_guide(guide: TriangulationGuide | None) -> TriangulationGuide | None: ...
def _refine_edges2(nodes: PointArray2, edges: EdgeArray, guide: TriangulationGuide | None) -> tuple[PointArray2, EdgeArray]: ...
def _refine_edges3(nodes: PointArray3, edges: EdgeArray, guide: TriangulationGuide | None) -> tuple[PointArray3, EdgeArray]: ...
def _triangulate_loop2(nodes: PointArray2, loop: tuple[int, ...], tolerance: float) -> list[FaceIndex]: ...
def _project_loop3(nodes: PointArray3, loop: tuple[int, ...], tolerance: float) -> PointArray2: ...
def _add_internal_edges(edges: EdgeArray, faces: FaceArray) -> EdgeArray: ...
```

Use `mesh_topology.edge_loops` rather than owning duplicate loop extraction.

## src/cady/operations/mesh_topology.py

Primary API:

```python
def boundary_edges(mesh: MeshArrays) -> list[EdgeIndex]: ...
def boundary_edges_from_faces(faces: Sequence[FaceIndex]) -> tuple[EdgeIndex, ...]: ...
def stitch_segments(segments: Iterable[EdgeIndex]) -> list[list[int]]: ...
def edge_loops(edges: object) -> tuple[tuple[int, ...], ...]: ...
def prune_dangling_edges(edges: Sequence[EdgeIndex]) -> tuple[EdgeIndex, ...]: ...
def compact_mesh_data(vertices: Sequence[Point3], faces: Sequence[FaceIndex], edges: Sequence[EdgeIndex]) -> tuple[tuple[Point3, ...], tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]: ...
```

Keep local type aliases for points, edges, faces, and mesh arrays.

## src/cady/operations/mesh_clipping.py

Primary API:

```python
def coerce_mesh(mesh_or_vertices: object, faces: object | None, edges: object | None = None) -> MeshArrays: ...
def close_planar_cap(mesh_or_vertices: object, faces: object | None = None, edges: object | None = None, plane_origin: object | None = None, plane_normal: object | None = None, *, tolerance: float = 1e-9, snap_tolerance: float | None = None) -> MeshArrays: ...
def close_boundary(mesh_or_vertices: object, faces: object | None = None, edges: object | None = None, *, tolerance: float = 1e-9) -> MeshArrays: ...
def cut_mesh_by_plane(mesh_or_vertices: object, faces: object | None = None, plane_origin: object | None = None, plane_normal: object | None = None, *, keep: KeepSide = "positive", cap: bool = True, tolerance: float = 1e-9) -> MeshArrays: ...
```

Important private helpers:

```python
def _cap_loops_to_faces(...) -> list[FaceIndex]: ...
def _project_loop(...) -> list[Point2]: ...
def _fit_plane_svd(...) -> tuple[Point3Array, Point3Array]: ...
def _clip_triangle(...) -> list[Point3Array]: ...
def _plane_points(...) -> list[Point3Array]: ...
```

This module uses `triangulate_mesh2` or `triangulate2` for planar cap fills.

## src/cady/operations/meshing.py

Primary API:

```python
def closed_polyline_mesh2(polyline: object, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh2: ...
def closed_polyline_mesh3(polyline: object, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def wireframe_mesh(wireframe: object, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def region_mesh(region: object, plane: Plane3, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def surface_region_mesh(region: object, surface: Surface3, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def extrusion_mesh(region: object, plane: Plane3, *, distance: float, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def region_loops_from_region(region: object, *, tolerance: float) -> tuple[tuple[tuple[Point2, ...], bool], ...]: ...
def mesh_from_triangles(triangles: tuple[Triangle3, ...]) -> Mesh3: ...
```

This module keeps region-loop extraction and extrusion policy, but delegates
fills to `triangulation.py`.

## src/cady/operations/lofting.py

Primary API:

```python
@dataclass(frozen=True, slots=True)
class LoftMesh:
    vertices: tuple[Point3, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...]

def loft_closed_curves3(start_curve: object, end_curve: object, *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def loft_closed_loops3(start: Sequence[Point3], end: Sequence[Point3], *, tolerance: float, guide: TriangulationGuide | None = None) -> Mesh3: ...
def loft_section_polylines(polylines: Iterable[Sequence[Point3]], *, tolerance: float) -> LoftMesh | None: ...
```

`loft_section_polylines` remains for current wireframe behavior until a broader
multi-section loft design replaces it.

## src/cady/operations/meshes.py

Temporary facade:

```python
from cady.operations.lofting import LoftMesh, loft_section_polylines
from cady.operations.mesh_clipping import close_boundary, close_planar_cap, coerce_mesh, cut_mesh_by_plane
from cady.operations.mesh_topology import boundary_edges, boundary_edges_from_faces, compact_mesh_data, prune_dangling_edges, stitch_segments
from cady.operations.meshing import extrusion_mesh, mesh_from_triangles, region_loops_from_region, region_mesh, surface_region_mesh, wireframe_mesh
```

Keep primitive helpers here for now if they are not part of this refactor.
Do not move linesplan code in this plan.

## Call-Site Updates

Expected direct import moves:

- `geometry/polyline.py`: use `triangulate_curve2` and `triangulate_curve3` or
  `closed_polyline_mesh2` and `closed_polyline_mesh3`.
- `geometry/region.py`: use `surface_region_mesh` from `meshing.py`.
- `geometry/body3.py`: use `extrusion_mesh` from `meshing.py`; leave primitive
  mesh imports alone.
- `geometry/mesh.py`: use clipping and topology functions from the new modules.
- `geometry/wireframe.py`: use `lofting.py`, `mesh_topology.py`, and
  `triangulation.py` directly.
- `operations/__init__.py`: re-export the public functions that remain part of
  the operations API.
