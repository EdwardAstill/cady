# Wireframe3D / Mesh3D split

## Current state

`Mesh3D` is a single type that holds `vertices`, `faces`, and optional
`edges`. It serves three roles: face-based mesh (faces populated), wireframe
(edges only, faces empty), and hybrid (both). Face-based methods like
`close_planar` silently no-op on wireframes because they detect boundaries
from faces.

## Target

Split into two focused types:

- **`Wireframe3D(vertices, edges)`** — edge-only, no faces field. Edge-based
  operations. Converts to `Mesh3D` via closing/triangulation.
- **`Mesh3D(vertices, faces, edges?)`** — faces present. Face-based
  operations. Optional `edges` field for wireframe display overlay (not
  topology).

## Wireframe3D

```python
@dataclass(frozen=True, slots=True)
class Wireframe3D:
    vertices: tuple[Vec3, ...]
    edges: tuple[EdgeIndex, ...]

    # Shared with Mesh3D
    def transformed(transform) -> Wireframe3D
    def mirror(origin, normal) -> Wireframe3D
    def bounds() -> tuple[Vec3, Vec3]
    def to_array(*, tolerance) -> ArrayMesh3
    def view(...)

    # Edge-based closing → Mesh3D
    def close_planar(origin, normal, *, tolerance) -> Mesh3D
    def triangulate_loops(*, tolerance) -> Mesh3D
```

### `close_planar(plane_origin, plane_normal, *, tolerance) -> Mesh3D`

Edge-based cap at a plane.

**Algorithm:**

1. Validate `tolerance > 0`. Accept `plane_origin` and `plane_normal` as
   `Point3Like` (tuple or Vec3).
2. Filter edges: collect edges where both endpoint vertices lie on the plane
   within `tolerance` (i.e. `abs(dot(vertex - origin, normal)) <= tolerance`).
   Skip edges where either endpoint is off-plane.
3. Stitch filtered edges into loops using the existing `_stitch_segments`
   from `mesh_cut.py` (make it importable — currently a private function).
4. For each loop:
   - Project loop vertices to the plane using `_project_loop`.
   - Triangulate the projected polygon with `_triangulate_loop`
     (ear-clipping, already in `mesh_cut.py`).
   - Map triangulated vertex indices back to original edge vertex indices.
5. Construct and return `Mesh3D(vertices, faces=cap_faces, edges=self.edges)`
   — the original wireframe edges are passed through for display overlay.
6. If no edges lie on the plane, raises `GeometryError`.

This does **not** project off-plane vertices — unlike the face-based
`Mesh3D.close_planar`, there are no faces to create gap strips from. Edges
that cross the plane are skipped. If the caller's vertices are slightly off
the plane, they should project the wireframe first:

```python
projected = wireframe.transformed(Transform3.project_to_plane(origin, normal))
mesh = projected.close_planar(origin, normal, tolerance=1e-3)
```

### `triangulate_loops(*, tolerance) -> Mesh3D`

Detect closed edge cycles and triangulate each into faces.

**Algorithm:**

1. Build an adjacency map from edges: `vertex_index -> set[neighbor_index]`.
2. Walk the graph to find cycles. Start at an unvisited vertex, follow
   neighbors depth-first until returning to the start. Mark visited vertices.
   Repeat for all vertices. Each cycle is a list of vertex indices in order.
3. Filter to cycles of length >= 3 (ignore degenerate 2-edge loops).
4. For each cycle:
   - Extract vertex positions.
   - Fit a best-fit plane via SVD (`_fit_plane_svd` from `mesh_cut.py`).
   - Project vertices to the plane.
   - Triangulate with `_triangulate_loop` (ear-clipping).
   - If a loop is non-planar beyond `tolerance`, raise `GeometryError`.
5. Construct and return `Mesh3D(vertices, faces, edges=self.edges)`.
6. If no closed loops >= 3 edges are found, raise `GeometryError`.

This is the wireframe equivalent of `Mesh3D.close_boundary` — it fills all
closed edge loops, not just holes in an existing face mesh.

## Mesh3D changes

- Keep `edges` field as optional display overlay (defaults to empty tuple).
  The vispy viewer already uses edges for wireframe render mode.
- `close_planar` and `close_boundary` unchanged — they already work on
  face-based meshes.
- Remove `from_dxf` classmethod. Replaced by `dxf.read_mesh(path)` at the
  facade layer. The old `from_dxf` conflated face-mesh and wireframe import;
  that conflation is exactly what we are fixing.
- Remove `_mesh_from_wire` helper — wire tuples from DXF become
  `Wireframe3D`, not `Mesh3D`.
- Keep `merged(cls, meshes: Iterable[Mesh3D]) -> Mesh3D` unchanged. It
  merges face-based meshes. Wireframes are not accepted.
- Add `to_wireframe() -> Wireframe3D`:

  ```python
  def to_wireframe(self) -> Wireframe3D:
      """Extract all edges from faces as a Wireframe3D."""
      edges = set()
      for a, b, c in self.faces:
          for start, end in ((a, b), (b, c), (c, a)):
              edges.add((min(start, end), max(start, end)))
      return Wireframe3D(self.vertices, tuple(sorted(edges)))
  ```

  This is a display/convenience method — it extracts all face edges, not
  just boundary edges.

## DXF import changes (detailed)

### `src/cady/files/dxf/__init__.py`

```python
@dataclass(frozen=True, slots=True)
class DxfImportResult:
    drawing: Drawing2D | None = None
    meshes: tuple[Mesh3D, ...] = ()          # 3DFACE / polyface
    wireframes: tuple[Wireframe3D, ...] = ()  # 3D POLYLINE wires
    skipped: tuple[DxfSkippedEntity, ...] = ()
```

The old `.wires` field (tuple of `tuple[Vec3, ...]`) is removed. Callers
that used `.wires` now get `.wireframes` with typed `Wireframe3D` objects.

```python
def read(path) -> DxfImportResult: ...
def read_drawing(path) -> Drawing2D: ...
def read_mesh(path) -> Mesh3D: ...          # unchanged — 3DFACE/polyface only
def read_wireframe(path) -> Wireframe3D: ...  # new — 3D POLYLINE wires only
```

`read_mesh(path)` now raises `ReadError` if the DXF contains no face data
(previously it also merged wire data into a `Mesh3D` with 0 faces).

`read_wireframe(path)` merges all wire tuples into a single `Wireframe3D`.

### `src/cady/files/dxf/reader.py`

Internal reader functions that currently return `tuple[Vec3, ...]` for wires
stay unchanged. The conversion to `Wireframe3D` happens in the facade layer
(`dxf/__init__.py`) to keep the reader import-light:

```python
def _wires_to_wireframes(wires: Iterable[tuple[Vec3, ...]]) -> tuple[Wireframe3D, ...]:
    result = []
    for wire in wires:
        if len(wire) >= 2:
            edges = tuple((i, i + 1) for i in range(len(wire) - 1))
            result.append(Wireframe3D(wire, edges))
    return tuple(result)
```

## DXF write

DXF write currently accepts `Drawing2D` only — no change needed for this
split.

## STL / STEP

STL and STEP write accept meshable targets (Body3D, Part, Assembly, Mesh3D,
Document). Wireframe3D has no faces, so it is not accepted by STL/STEP
writers. The user must call `wireframe.close_planar(...)` or
`wireframe.triangulate_loops(...)` first to get a Mesh3D.

## Body3D / Part / Assembly

Unchanged — they evaluate to `Mesh3D` via `to_mesh(tolerance)`. They don't
interact with `Wireframe3D`.

## ArrayMesh3 (ops layer)

Unchanged. `ArrayMesh3` already stores `vertices`, `faces`, `edges`
separately. Both `Wireframe3D.to_array()` and `Mesh3D.to_array()` return
`ArrayMesh3`. Ops functions operate on `ArrayMesh3`.

## Visualisation

- `Scene.add(target)` already accepts `Mesh3D` via `SceneTarget` union. Add
  `Wireframe3D` to the union.
- Vispy viewer already handles `Mesh3D` with edges for wireframe mode.
  `Wireframe3D` can be rendered the same way (edges only).
- `Wireframe3D.view(...)` wraps self in a Scene and opens viewer.

## Affected files

| File | Change |
|------|--------|
| `src/cady/geometry3d/wireframe.py` | New — `Wireframe3D` class |
| `src/cady/geometry3d/mesh.py` | Remove `from_dxf` (or keep as convenience that calls `dxf.read_mesh`). Rename `_mesh_from_wire` → `_wireframe_from_wire_tuple`. |
| `src/cady/geometry3d/__init__.py` | Export `Wireframe3D` |
| `src/cady/__init__.py` | Export `Wireframe3D` |
| `src/cady/files/dxf/__init__.py` | `DxfImportResult.wires` → `.wireframes`. Add `read_wireframe()`. |
| `src/cady/files/dxf/reader.py` | Wire→`Wireframe3D` conversion |
| `src/cady/view/scene.py` | Add `Wireframe3D` to `SceneTarget` |
| `src/cady/visualisation/vispy_viewer.py` | Handle `Wireframe3D` in mesh buffer extraction |
| `tests/geometry3d/test_wireframe.py` | New tests |
| `tests/geometry3d/test_mesh.py` | Add conversion tests |
| `tests/geometry3d/test_mesh_close.py` | Add edge-based close tests |
| `tests/files/test_new_file_facades.py` | Update DXF import assertions |
| `tests/test_smoke_import.py` | Add `Wireframe3D` to expected exports |
| `tests/examples/test_visualise_3d.py` | Update mirror-mesh assertions |
| `examples/linesplan/close-mirror-mesh.py` | Use `Wireframe3D.close_planar` |

## Implementation order

1. Create `Wireframe3D` with `vertices`, `edges`, `transformed`, `mirror`,
   `bounds`, `to_array`, `view`.
2. Add `Wireframe3D.close_planar` — edge-based planar cap → `Mesh3D`.
3. Add `Wireframe3D.triangulate_loops` — detect closed edge cycles,
   triangulate → `Mesh3D`.
4. Update DXF reader: `wires` → `wireframes` in `DxfImportResult`. Add
   `read_wireframe()`.
5. Update `Mesh3D`: remove `from_dxf`, add `to_wireframe()`.
6. Add `Wireframe3D` to exports, `SceneTarget`, visualisation.
7. Update tests.
8. Update `close-mirror-mesh.py` example.

## Test strategy

### `tests/geometry3d/test_wireframe.py` (new)

| Test | What |
|------|------|
| `test_wireframe_construction` | Valid edges, negative indices rejected, out-of-range edges rejected |
| `test_wireframe_empty` | Empty vertices/edges is valid |
| `test_wireframe_transformed` | Transform applies to vertices, edges unchanged |
| `test_wireframe_mirror` | Mirror flips vertices across plane, edges unchanged |
| `test_wireframe_bounds` | Empty bounds raise, non-empty compute correctly |
| `test_wireframe_to_array` | Round-trip through ArrayMesh3 (faces empty) |
| `test_wireframe_close_planar_square` | 4-edge square on plane → Mesh3D with 2 triangles |
| `test_wireframe_close_planar_no_edges_on_plane` | Raises GeometryError |
| `test_wireframe_close_planar_partial` | Only edges on plane capped, others ignored |
| `test_wireframe_close_planar_multiple_loops` | Two separate loops on same plane |
| `test_wireframe_triangulate_loops_square` | Closed 4-edge loop → Mesh3D with 2 triangles |
| `test_wireframe_triangulate_loops_no_cycles` | Open chain → raises GeometryError |
| `test_wireframe_triangulate_loops_non_planar` | Non-planar loop → raises GeometryError |
| `test_wireframe_triangulate_loops_multiple_cycles` | Two separate cycles → both triangulated |

### `tests/geometry3d/test_mesh.py` (add)

| Test | What |
|------|------|
| `test_mesh_to_wireframe` | Mesh3D with faces → Wireframe3D with correct edges |
| `test_mesh_to_wireframe_empty_faces` | Mesh3D with no faces → empty Wireframe3D |
| `test_mesh_from_dxf_removed` | `Mesh3D.from_dxf` no longer exists |

### `tests/geometry3d/test_mesh_close.py` (add)

| Test | What |
|------|------|
| `test_wireframe_close_planar_integration` | Full edge-based close workflow |

### `tests/files/test_new_file_facades.py` (update)

| Test | What |
|------|------|
| `test_dxf_import_result_has_wireframes_not_wires` | `.wireframes` field exists, `.wires` does not |
| `test_dxf_read_wireframe` | `dxf.read_wireframe(...)` returns `Wireframe3D` |
| `test_dxf_read_mesh_no_wire_data` | `dxf.read_mesh(...)` on wire-only DXF raises `ReadError` |

### `tests/test_smoke_import.py` (update)

- `Wireframe3D` in expected public exports
- Assert old `.wires` name not accessible on `DxfImportResult`

### `tests/view/test_object_view_methods.py` (update)

- `Wireframe3D.view(...)` smoke test

## Acceptance criteria

1. `Wireframe3D` is a frozen dataclass with `vertices` and `edges` (no faces field)
2. `wireframe.close_planar(origin, normal, *, tolerance)` caps edges on the
   plane and returns `Mesh3D` with triangulated faces
3. `wireframe.triangulate_loops(*, tolerance)` finds closed edge cycles and
   triangulates them into a `Mesh3D`
4. `mesh.to_wireframe()` extracts edges from faces into a `Wireframe3D`
5. `Mesh3D.from_dxf` is removed; `dxf.read_mesh(path)` and
   `dxf.read_wireframe(path)` are the public API
6. `DxfImportResult` has `.wireframes` field, not `.wires`
7. All 15 existing `test_mesh_close` tests still pass
8. All existing geometry3d, mesh, dxf read tests pass
9. `close-mirror-mesh.py` runs with `--no-view` and produces a closed mesh
   with faces > 0
10. pyright 0 errors, ruff clean

## Validation

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ -x -v
PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py -x -v
PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/view/ -x -v
PYTHONPATH=src .venv/bin/pytest -q tests/examples/test_visualise_3d.py -x -v
PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py --no-view
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

## Non-goals

- Do not change `ArrayMesh3` — it stays with all three fields.
- Do not add `snap_tolerance` to `Wireframe3D.close_planar` — the edge-based
  algorithm caps directly from edges on the plane.
- Do not change STL/STEP writer contracts for `Wireframe3D`.
- Do not remove `edges` field from `Mesh3D` — it serves a display role.
