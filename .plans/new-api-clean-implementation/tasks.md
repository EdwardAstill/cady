# Implementation Tasks

These tasks are ordered for a clean replacement. Do not add compatibility
wrappers for removed API names.

## 1. Reset Public API Expectations

Actions:

- Rewrite `tests/test_smoke_import.py` around the new top-level names.
- Add `tests/conventions/test_public_api_removed.py`.
- Assert `Model`, `DxfDrawing`, `StlMesh`, `Shape2D`, `Shape3D`, `Rectangle`,
  `Prism`, `Sphere`, `Extrusion`, and `Revolution` are not exported.
- Assert `write_model` is absent from DXF/STL/STEP facades.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/conventions/test_public_api_removed.py
```

## 2. Add Error Tiers

Actions:

- Replace `src/cady/errors.py` with the new error hierarchy.
- Rewrite `tests/errors/test_error_tiers.py` for `GeometryError`,
  `DrawingError`, `ProductError`, `ViewError`, `ReadError`, and `WriteError`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/errors
```

## 3. Build `geometry2d`

Actions:

- Create `src/cady/geometry2d/`.
- Implement `Line2D`, `Arc2D`, `Spline2D`, `Polyline2D`, `Circle2D`,
  `Ellipse2D`, `ClosedPolyline2D`, and `Profile2D`.
- Add factories in `geometry2d/factories.py`.
- Move useful logic from old `shapes2d.py` into new classes.
- Keep `Rectangle` out of the public/core class model; rectangle is a profile
  factory.
- Add tests under `tests/geometry2d/`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry2d tests/conventions/test_import_boundaries.py
```

## 4. Build `geometry3d` Core

Actions:

- Create `src/cady/geometry3d/`.
- Implement `Frame3D`, `Face3D`, `Mesh3D`, feature records, and `Body3D`.
- Port `FacetedMesh` behavior into `Mesh3D`.
- Implement body factories for `box`, `cylinder`, `sphere`, and profile
  extrusion.
- Implement `Body3D.to_mesh(tolerance=...)`.
- Add tests under `tests/geometry3d/`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d tests/numeric
```

## 5. Clean `ops` Dependency Direction

Actions:

- Remove domain imports from `src/cady/ops/tessellate.py` and
  `src/cady/ops/transforms.py`.
- Split semantic evaluation into `ops/evaluate2d.py` and `ops/evaluate3d.py`
  or into methods that unpack domain data before calling primitive ops.
- Update convention tests so there are no legacy exceptions for ops importing
  domain modules.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry2d tests/geometry3d tests/conventions/test_import_boundaries.py
```

## 6. Build `drawing`

Actions:

- Create `src/cady/drawing/`.
- Implement `Layer`, `DrawingEntity`, `Drawing2D`, text, hatch, block, insert,
  dimstyle, and dimension entities.
- Port useful drawing validation and dimension calculations from old
  `domain/drawing.py`.
- Make `Drawing2D` immutable with tuple fields and methods returning new
  drawings.
- Remove public `DxfDrawing` from exports.
- Add tests under `tests/drawing/`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/drawing tests/conventions/test_import_boundaries.py
```

## 7. Update DXF Writer To `Drawing2D`

Actions:

- Change DXF render internals to accept `Drawing2D`.
- Update entity emission from old `Shape2D` to `Curve2D`, `ClosedCurve2D`, and
  `Profile2D`.
- Update hatch/block/dimension/table render helpers to the new drawing classes.
- Replace `dxf.render_drawing`/`write_drawing`/`write_model` with
  `dxf.render` and `dxf.write`.
- Rewrite DXF writer tests for `Drawing2D`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/drawing tests/files/test_dxf_write.py tests/write
```

## 8. Update DXF Reader To `Drawing2D` And `Mesh3D`

Actions:

- Change 2D parser return type from `DxfDrawing` to `Drawing2D`.
- Change 3D parser return type from `FacetedMesh` to `Mesh3D`.
- Add `DxfImportResult` for mixed reads.
- Keep first-pass DXF scope: 2D to drawing, supported 3D facets/polyfaces to
  mesh, skipped ACIS entities reported.
- Rewrite DXF reader tests.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/files/test_dxf_read_drawing.py tests/files/test_dxf_read_mesh.py
```

## 9. Build `product`

Actions:

- Create `src/cady/product/`.
- Implement `Material`, `Part`, `PartInstance`, `AssemblyInstance`, and
  `Assembly`.
- Implement assembly flattening and cycle detection.
- Apply `Pose3D`/`Transform3` to placed meshes.
- Add tests under `tests/product/`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/product tests/geometry3d
```

## 10. Build `view`

Actions:

- Create `src/cady/view/`.
- Implement `DisplayStyle`, `Camera`, `AmbientLight`, `DirectionalLight`,
  `PointLight`, `SceneObject`, and `Scene`.
- Keep these objects backend-independent and import-light.
- Add tests under `tests/view/`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/view tests/conventions/test_import_boundaries.py
```

## 11. Add Optional `Document`

Actions:

- Implement `src/cady/document.py`.
- Store drawings, parts, assemblies, scenes, units, and metadata.
- Keep `Document` optional; no workflow should require it.
- Add tests under `tests/document/`.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/document
```

## 12. Update STL Facade

Actions:

- Replace `StlMesh` public workflow with `Mesh3D` and `stl.write(...)`.
- Support `Mesh3D`, `Body3D`, `Part`, `Assembly`, and `Document`.
- Reuse low-level ASCII/binary STL emitters.
- Rewrite STL tests.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/files/test_stl_write.py tests/write/test_stl.py
```

## 13. Update STEP Facade

Actions:

- Replace `step.write_model` with `step.render` and `step.write`.
- Translate supported `Body3D` features to existing B-rep writer internals.
- Support `Part` and flattened `Assembly`.
- Keep STEP face/member read API.
- Rewrite STEP writer tests.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/files/test_step_write.py tests/write/test_step.py tests/read
```

## 14. Update Visualisation Adapters

Actions:

- Update visualisation functions to consume `Scene`.
- Allow direct target viewing by wrapping target in a default `Scene`.
- Map `Camera` and `Light` values into backend settings where supported.
- Remove imports of old `Model`, `Part.solids`, `Shape2D`, and `Shape3D`.
- Rewrite visualisation tests.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/visualisation tests/view
```

## 15. Replace Package Exports And Delete Legacy Packages

Actions:

- Update `src/cady/__init__.py` to export only new names.
- Delete or empty `src/cady/domain/` and `src/cady/build/` if no longer used.
- Remove old source files that only support removed API names.
- Update `tests/conventions/test_stdlib_only.py` package exceptions if needed
  for current optional dependencies.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/conventions
```

## 16. Rewrite Docs And Examples

Actions:

- Update `docs/api.md`, `docs/object-model.md`, `docs/getting-started.md`,
  `docs/examples.md`, and `README.md`.
- Lead with direct `Profile2D`, `Drawing2D`, `Body3D`, `Part`, `Assembly`, and
  `Scene` examples.
- Remove `Model`, `DxfDrawing`, `StlMesh`, and old primitive examples.
- Rewrite example scripts/tests.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/examples
```

## 17. Full Verification And Cleanup

Actions:

- Run all tests.
- Run pyright and ruff.
- Remove stale pycache, obsolete golden files, obsolete docs, and old test
  directories if they no longer apply.
- Review top-level exports and docs for any old names.

Verification:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
rg -n "\\b(Model|DxfDrawing|StlMesh|Shape2D|Shape3D|Rectangle|Prism|Sphere|Extrusion|Revolution|write_model)\\b" src/cady tests docs README.md
```
