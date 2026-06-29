# Tasks

## 1. Extract Mesh Topology

Move topology-only helpers from `operations/meshes.py` into
`operations/mesh_topology.py`:

- `boundary_edges`
- `boundary_edges_from_faces`
- `stitch_segments`
- `edge_loops`
- `prune_dangling_edges`
- `compact_mesh_data`

Update imports in `operations/meshes.py`, `geometry/mesh.py`, and
`geometry/wireframe.py` as needed.

Verification:

```bash
.venv/bin/pytest -q tests/geometry/test_mesh_close.py tests/geometry/test_mesh3.py tests/geometry/test_wireframe3.py
.venv/bin/ruff check src/cady/operations/mesh_topology.py src/cady/operations/meshes.py src/cady/geometry/mesh.py src/cady/geometry/wireframe.py
```

## 2. Extract Mesh Clipping

Move existing mesh clipping and closure functions into
`operations/mesh_clipping.py`:

- `coerce_mesh`
- `close_planar_cap`
- `close_boundary`
- `cut_mesh_by_plane`

Move only the private helpers those functions need. Reuse
`mesh_topology.py` for boundary edges and loop stitching.

Verification:

```bash
.venv/bin/pytest -q tests/operations/test_mesh_cut.py tests/geometry/test_mesh_close.py
.venv/bin/pyright src/cady/operations/mesh_clipping.py src/cady/operations/meshes.py src/cady/geometry/mesh.py
```

## 3. Redesign Triangulation API

Update `operations/triangulation.py` with:

- `TriangulationGuide`
- `triangulate_curve2`
- `triangulate_curve3`
- `triangulate_mesh2`
- `triangulate_mesh3`
- compatibility wrappers `triangulate2` and `triangulate3`

Implement `target_edge_length` and `max_edge_length` boundary refinement.
Reject unsupported `max_area` and `min_angle_degrees` with a clear
`NotImplementedError` or defer adding those fields until they are supported.

Verification:

```bash
.venv/bin/pytest -q tests/operations/test_triangulation.py tests/geometry/test_geometry_curves2.py tests/geometry/test_curves3.py
.venv/bin/pyright src/cady/operations/triangulation.py tests/operations/test_triangulation.py
```

## 4. Extract CAD Meshing

Create `operations/meshing.py` for CAD-facing mesh construction:

- `closed_polyline_mesh2`
- `closed_polyline_mesh3`
- `wireframe_mesh`
- `region_mesh`
- `surface_region_mesh`
- `extrusion_mesh`
- `region_loops_from_region`
- `mesh_from_triangles`

Update geometry modules to import these names directly where appropriate.
Keep `operations/meshes.py` re-exporting moved functions during the transition.

Verification:

```bash
.venv/bin/pytest -q tests/geometry/test_region3.py tests/geometry/test_body3.py tests/geometry/test_wireframe3.py tests/geometry/test_curves3.py tests/geometry/test_geometry_curves2.py
.venv/bin/ruff check src/cady/operations/meshing.py src/cady/geometry/polyline.py src/cady/geometry/region.py src/cady/geometry/body3.py src/cady/geometry/wireframe.py
```

## 5. Extract Lofting

Create `operations/lofting.py` with:

- `LoftMesh`
- `loft_closed_curves3`
- `loft_closed_loops3`
- existing `loft_section_polylines` compatibility behavior

Keep the first closed-loop loft implementation simple: resample both loops to a
compatible count, connect corresponding vertices, and preserve loop/display
edges.

Verification:

```bash
.venv/bin/pytest -q tests/geometry/test_wireframe3.py tests/geometry/test_linesplan_meshing.py
.venv/bin/pyright src/cady/operations/lofting.py src/cady/geometry/wireframe.py
```

## 6. Keep `meshes.py` As A Facade

Reduce `operations/meshes.py` to imports/re-exports for the moved functions
while leaving primitive and linesplan code in place for now if moving it would
increase scope.

Update `operations/__init__.py` exports for new public triangulation names.

Verification:

```bash
.venv/bin/pytest -q tests/test_smoke_import.py tests/conventions/test_import_boundaries.py tests/conventions/test_stdlib_only.py tests/conventions/test_public_api_removed.py
.venv/bin/ruff check src/cady/operations
```

## 7. Add Focused Tests

Add or update tests for:

- `triangulate_curve2` on a closed square polyline.
- `triangulate_curve3` on a planar closed square polyline.
- `triangulate_curve3` rejecting non-planar closed curves.
- `triangulate_mesh2` returning faces and internal edges.
- `triangulate_mesh3` returning faces and internal edges for planar input.
- guide-driven boundary refinement with `max_edge_length`.
- unsupported guide options failing explicitly.

Verification:

```bash
.venv/bin/pytest -q tests/operations/test_triangulation.py
```

## 8. Final Gates

Run the narrow and convention gates after each extraction, then the full gates
when the split is complete.

Verification:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
git status --short
```
