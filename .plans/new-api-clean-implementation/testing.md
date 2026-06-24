# Testing Strategy

## Test Layout

Replace the legacy test layout where needed:

```text
tests/geometry2d/
  test_curves.py
  test_profiles.py
  test_factories.py

tests/geometry3d/
  test_frame.py
  test_face.py
  test_body_features.py
  test_mesh.py

tests/drawing/
  test_drawing2d.py
  test_layers.py
  test_blocks.py
  test_dimensions.py
  test_hatch.py

tests/product/
  test_part.py
  test_assembly.py
  test_flatten.py

tests/view/
  test_camera.py
  test_lights.py
  test_scene.py

tests/document/
  test_document.py

tests/files/
  test_dxf_read_drawing.py
  test_dxf_read_mesh.py
  test_dxf_write.py
  test_stl_write.py
  test_step_write.py

tests/conventions/
  test_import_boundaries.py
  test_stdlib_only.py
  test_public_api_removed.py

tests/visualisation/
  test_scene_view.py
```

Delete or rewrite tests under `tests/model`, `tests/scene`, and old
`tests/domain` that only assert `Model`, `DxfDrawing`, `StlMesh`, `Shape2D`,
`Shape3D`, `Rectangle`, `Prism`, `Sphere`, `Extrusion`, or `Revolution`.

## Coverage Targets

### Public API Removal

Assert removed names are gone:

```python
assert not hasattr(cady, "Model")
assert not hasattr(cady, "DxfDrawing")
assert not hasattr(cady, "StlMesh")
```

Assert facade functions are gone:

```python
assert not hasattr(cady.files.dxf, "write_model")
assert not hasattr(cady.files.stl, "write_model")
assert not hasattr(cady.files.step, "write_model")
```

### Geometry2D

- validate `Line2D`, `Arc2D`, `Circle2D`, `Ellipse2D`, `Polyline2D`,
  `ClosedPolyline2D`;
- validate `Profile2D` outer/holes;
- assert factories return new concepts;
- assert `to_array(tolerance=...)` requires positive tolerance;
- assert rectangle factory returns `Profile2D`.

### Drawing

- direct `Drawing2D` authoring with layers;
- text/hatch/block/insert/dimension entities;
- bounds include all drawing content;
- drawing values are frozen;
- mutator-style methods return new drawings;
- no `DxfDrawing` public object.

### Geometry3D

- `Frame3D` derives orthonormal axes and rejects degenerate inputs;
- `Face3D.from_profile`, `from_points`, and `convex_hull` behavior;
- `Body3D` factories and features;
- body evaluation to `Mesh3D` for box, cylinder, sphere, and extrusion;
- `Mesh3D` validation and transforms.

### Product

- `Part` accepts bodies and rejects non-body values;
- multi-body parts merge mesh output;
- `Assembly` places parts;
- nested assembly flattening;
- cycle detection;
- duplicate instance name policy.

### View

- `Camera.look_at` validates position/target/up;
- orthographic and perspective cameras validate their parameters;
- ambient/directional/point lights validate color/intensity/direction;
- `Scene` accepts drawings, bodies, parts, assemblies, and meshes;
- active camera references are valid.

### DXF

- `dxf.read_drawing` imports `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `TEXT`,
  and `MTEXT` into `Drawing2D`;
- `dxf.read_mesh` imports `3DFACE` triangles/quads and polyface polylines into
  `Mesh3D`;
- `dxf.read` reports skipped ACIS-backed entities;
- `dxf.write` emits valid R2018 DXF from `Drawing2D`;
- golden smoke DXF updated to new public objects.

### STL

- binary and ASCII STL write from `Mesh3D`;
- STL write from `Body3D`, `Part`, and `Assembly`;
- empty mesh/part/assembly policies are tested;
- triangle normals remain valid.

### STEP

- STEP write from supported `Body3D` features;
- STEP write from `Part`;
- STEP write from flattened `Assembly`;
- unsupported features raise `WriteError`;
- existing STEP face/member read tests remain.

### Visualisation

- optional imports still smoke-test correctly;
- `view(scene, ...)` can save a basic image using the matplotlib backend;
- direct target view creates a default scene internally.

## Convention Tests

Update import-boundary tests to the new packages:

- `geometry2d`, `geometry3d`, `drawing`, `product`, `view`, and `document`
  do not import optional backends or NumPy at module scope unless an explicit
  exception is approved.
- `numeric` does not import any semantic package.
- `ops` does not import semantic packages.
- `files` does not import optional backends or NumPy at module scope.
- Runtime import allowlist matches `pyproject.toml`.

Add a convention test that every public `to_array`, `to_mesh`, `render`, and
`write` path has an explicit keyword-only `tolerance` parameter where
discretisation is involved.

## Verification Commands

Focused commands:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry2d
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d
PYTHONPATH=src .venv/bin/pytest -q tests/drawing
PYTHONPATH=src .venv/bin/pytest -q tests/product
PYTHONPATH=src .venv/bin/pytest -q tests/view
PYTHONPATH=src .venv/bin/pytest -q tests/files
PYTHONPATH=src .venv/bin/pytest -q tests/conventions
PYTHONPATH=src .venv/bin/pytest -q tests/visualisation
```

Full gates:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```
