# Triangulation And Meshing Split

## Purpose

Refactor the current triangulation and mesh-operation code into focused modules
with clear ownership:

- Triangulation creates triangular elements for closed curves or constrained
  node/edge meshes.
- Meshing creates CAD meshes from regions, surfaces, wireframes, and extrusion
  inputs.
- Mesh topology owns graph-like helpers for edges, loops, compacting, and
  pruning.
- Mesh clipping owns cutting and capping existing triangle meshes.
- Lofting owns mesh generation between closed curves.

The target is a clearer API and easier future support for triangle guides such
as approximate element size and angle constraints.

## Definitions

Triangulating a curve means sampling or using a closed curve boundary and
filling it with triangle elements.

Triangulating a mesh means taking existing nodes and constraint edges and
ensuring the result has triangular elements by adding internal edges and faces
where appropriate.

`triangulate_curve3` is planar unless a surface-aware meshing function is used.
An arbitrary non-planar closed 3D curve does not uniquely define a filled
surface.

## Guide Object

Add one operation-local guide object:

```python
@dataclass(frozen=True, slots=True)
class TriangulationGuide:
    target_edge_length: float | None = None
    max_edge_length: float | None = None
    max_area: float | None = None
    min_angle_degrees: float | None = None
```

Initial implementation should support `target_edge_length` and
`max_edge_length` by refining boundary edges before triangulation. `max_area`
can be supported after the core split by subdividing large triangles.
`min_angle_degrees` should not be silently accepted until the algorithm can
actually enforce it.

## Public Operation API

`src/cady/operations/triangulation.py` should expose:

```python
TriangulationGuide

triangulate_curve2(curve, *, tolerance, guide=None) -> Mesh2
triangulate_curve3(curve, *, tolerance, guide=None) -> Mesh3

triangulate_mesh2(nodes, edges, *, tolerance=1e-9, guide=None) -> tuple[nodes, edges, faces]
triangulate_mesh3(nodes, edges, *, tolerance=1e-9, guide=None) -> tuple[nodes, edges, faces]

triangulate2(nodes, edges, *, tolerance=1e-9, guide=None) -> tuple[nodes, faces]
triangulate3(nodes, edges, *, tolerance=1e-9, guide=None) -> tuple[nodes, faces]
```

`triangulate2` and `triangulate3` remain compatibility wrappers over
`triangulate_mesh2` and `triangulate_mesh3`.

Curve functions may late-import `Mesh2` and `Mesh3`, but the core mesh functions
should remain array-based.

## Module Boundaries

### triangulation.py

Owns:

- `TriangulationGuide`
- curve triangulation entry points
- constrained node/edge triangulation entry points
- 2D ear clipping or equivalent simple polygon triangulation
- planar 3D projection for closed 3D edge loops
- edge refinement driven by guide size constraints

Does not own:

- mesh clipping
- cap closure of existing meshes
- lofting
- linesplan classification
- primitive body meshing
- region or surface policy beyond closed-curve filling

### meshing.py

Owns CAD-facing conversion helpers:

- `region_mesh`
- `surface_region_mesh`
- `wireframe_mesh`
- `closed_polyline_mesh2`
- `closed_polyline_mesh3`
- `extrusion_mesh`
- `region_loops_from_region`
- `mesh_from_triangles`

This module calls `triangulation.py` for fill triangulation.

### lofting.py

Owns closed-curve lofting:

- `LoftMesh`
- `loft_closed_curves3`
- `loft_closed_loops3`
- compatibility wrapper for the current section-polyline loft helper if needed

The first implementation should target two closed loops. Multi-section lofting
can stay behind the existing helper until separately redesigned.

### mesh_clipping.py

Owns operations on existing triangle meshes:

- `cut_mesh_by_plane`
- `close_planar_cap`
- `close_boundary`
- local cap triangulation helpers
- triangle-plane clipping helpers

### mesh_topology.py

Owns topology helpers:

- `boundary_edges`
- `boundary_edges_from_faces`
- `stitch_segments`
- `edge_loops`
- `prune_dangling_edges`
- `compact_mesh_data`

No CAD semantics, no surface policy, no sampling.

### meshes.py

Becomes a compatibility facade during the refactor. It should import and
re-export the moved functions so existing call sites can be migrated in small
steps. After callers move, it can be deleted or left as a thin public facade.

## Dependency Rules

- Core triangulation and topology functions operate on arrays, tuples, and local
  dataclasses.
- Operations modules may import `numpy` and stdlib only at module scope, plus
  other `cady.operations` and `cady.utils` helpers.
- If an operations function returns `Mesh2` or `Mesh3`, import the geometry type
  inside the function.
- `geometry` modules call operation helpers; operation modules must not import
  drawing, product, view, or files.

## Done Criteria

- The new modules exist with the ownership described above.
- `triangulation.py` exposes the new curve and mesh triangulation API.
- Existing behavior for polyline, region, extrusion, cap closure, wireframe
  loop triangulation, and mesh clipping is preserved.
- `meshes.py` no longer contains the implementation bodies for topology,
  clipping, triangulation, lofting, and region meshing.
- Public imports from `cady.operations` remain stable where currently tested.
- New tests cover `triangulate_curve2`, `triangulate_curve3`,
  `triangulate_mesh2`, `triangulate_mesh3`, guide edge refinement, and the
  module split.
