# cady — Agent Context

cady is a small native CAD geometry package for building format-blind geometry,
emitting DXF R2018, binary/ASCII STL, or AP214 STEP, and extracting elementary
surface data from STEP files.

## Principles

1. **Semantic > numeric.** Keep authoring geometry as domain objects (`Circle`,
   `Rectangle`, `Extrusion`). Convert with `.to_array(tolerance=1e-3)` only at
   calculation boundaries.
2. **Domain is import-light.** `cady.domain` must not import NumPy, matplotlib,
   pyvista, or `cady.visualisation` at module scope. Validate with
   `tests/conventions/test_import_boundaries.py`.
3. **Immutable domain objects.** All shapes, vectors, and metadata are frozen
   dataclasses (`frozen=True`). Transforms return new instances; never mutate.
4. **Tolerance is explicit.** Every `to_array(...)`, tessellation, and export
   function accepts `tolerance` as a keyword argument. No hidden defaults.
5. **No external deps at runtime.** Runtime imports are limited to `cady`,
   `numpy`, and `steputils`. `matplotlib` and `pyvista` are optional extras
   gated behind `[visualisation]`. Enforced by
   `tests/conventions/test_stdlib_only.py`.
6. **Layers are named, not numbered.** Drawings assign entities to named layers
   with color and linetype. DXF writers map these to DXF layer tables.

## Architecture

```text
cady.build        factories (line, circle, rectangle, sphere, prism, …)
cady.domain       semantic objects (Vec2, Vec3, Shape2D, Shape3D, Model, Part, …)
cady.ops          geometry algorithms (transforms, tessellation, profiles, mesh_cut)
cady.numeric      NumPy-backed evaluated geometry (ArrayPolygon2, ArrayMesh3, Transform3, …)
cady.files        format I/O (DXF writer, STL writer, STEP reader/writer)
cady.visualisation optional plotting (matplotlib, pyvista)
cady.errors       exception hierarchy (CadError, SceneError, WriteError)
```

### Dependency rules (enforced by CI)

| Rule | Test |
|------|------|
| `cady.domain` must not import `numpy` or `cady.visualisation` at module scope | `test_import_boundaries.py::test_domain_does_not_import_visualisation_or_numpy_at_module_scope` |
| `cady.numeric` must not import `cady.domain` | `test_import_boundaries.py::test_numeric_does_not_import_domain` |
| `cady.ops` must not import `cady.domain` (except legacy compat files) | `test_import_boundaries.py::test_new_ops_modules_do_not_import_domain` |
| `cady.files` must not import `numpy` or `cady.visualisation` at module scope | `test_import_boundaries.py::test_files_do_not_import_visualisation_or_numpy_at_module_scope` |
| Runtime imports limited to `cady`, `numpy`, `steputils` (+ `matplotlib`/`pyvista` in `visualisation` only) | `test_stdlib_only.py` |
| Old packages (`geom`, `model`, `scene`, `write`, `read`, `exporters`, `importers`) must be removed | `test_smoke_import.py::test_old_subpackages_are_removed` |

The intended conversion boundary:

```text
domain_object.to_array(tolerance=1e-3) → ops.primitive_function → numeric result
```

### Key files

| File | Purpose |
|------|---------|
| `src/cady/__init__.py` | Public API re-exports |
| `src/cady/domain/base.py` | `Shape2D`, `Shape3D` ABCs, `Axis` types, `parse_axis`, `axis_vector` |
| `src/cady/domain/vec.py` | `Vec2`, `Vec3` frozen dataclasses |
| `src/cady/domain/shapes2d.py` | `Line`, `Arc`, `Circle`, `Rectangle`, `Polyline`, `Spline`, `Path` |
| `src/cady/domain/shapes3d.py` | `Sphere`, `Prism`, `Extrusion`, `Revolution` |
| `src/cady/domain/drawing.py` | `DxfDrawing`, `Layer`, `BlockDefinition`, `DimStyle`, dimension entities |
| `src/cady/domain/mesh.py` | `StlMesh`, `triangles_to_array_mesh`, `array_mesh_to_triangles` |
| `src/cady/domain/model.py` | `Model`, `Drawing2D`, `Part`, `Assembly`, `ModelLayer`, `ModelMetadata` |
| `src/cady/build/factories.py` | Convenience constructors (`line(…)`, `circle(…)`, …) |
| `src/cady/ops/transforms.py` | `translate2`, `rotate2`, `scale2`, `mirror2`, `translate3`, etc. |
| `src/cady/ops/tessellate.py` | `extrusion_to_triangles`, `curves_to_polyline`, `sphere_to_triangles`, … |
| `src/cady/ops/profiles.py` | `midpoint`, `offset_point`, `perpendicular` |
| `src/cady/ops/mesh_cut.py` | `cut_mesh_by_plane` |
| `src/cady/numeric/paths2d.py` | `ArrayPolyline2`, `ArrayPolygon2` |
| `src/cady/numeric/mesh3d.py` | `ArrayMesh3`, `ArrayPolyline3` |
| `src/cady/numeric/transform.py` | `Transform2`, `Transform3`, `Pose3` |
| `src/cady/numeric/validation.py` | `as_points2`, `as_points3`, `as_faces`, `as_matrix3`, `as_matrix4` |
| `src/cady/numeric/curves2d.py` | `ArrayBezierSpline2`, `evaluate_bezier_spline2`, `sample_bezier_spline2` |
| `src/cady/numeric/bounds.py` | `bounds2`, `bounds3` |
| `src/cady/numeric/types.py` | NumPy type aliases (`FloatArray`, `PointArray2`, `FaceArray`, etc.) |
| `src/cady/files/dxf/sections.py` | `render_dxf`, `write_dxf` — main DXF emitter |
| `src/cady/files/dxf/document.py` | DXF bounds calculation |
| `src/cady/files/step/document.py` | `render_step` — AP214 STEP writer |
| `src/cady/files/step/brep.py` | B-rep construction for `Prism` and `Extrusion` |
| `src/cady/files/step/faces.py` | `read_step` — STEP face parser |
| `src/cady/files/step/members.py` | `extract_members_from_faces` — structural member extraction |
| `src/cady/files/step/ids.py` | `IdAllocator` — STEP entity ID management |
| `src/cady/files/stl/ascii.py` | ASCII STL writer |
| `src/cady/files/stl/binary.py` | Binary STL writer |

## Module boundaries when editing

### Adding a 2D shape

1. Subclass `Shape2D` in `cady.domain.shapes2d` (frozen dataclass)
2. Implement `bounds()`, `points()`, `close()`, `_transform2()`, `to_array()`
3. Add factory to `cady.build.factories`
4. Re-export from `cady.domain.__init__` and `cady.__init__`
5. Add tests under `tests/domain/` or `tests/geom/`
6. Run import boundary tests

### Adding a 3D shape

1. Subclass `Shape3D` in `cady.domain.shapes3d` (frozen dataclass)
2. Implement `bounds()`, `_transform3()`, `to_array()`
3. Add factory to `cady.build.factories`
4. Re-export from `cady.domain.__init__` and `cady.__init__`
5. If STEP export is desired, add case to `cady.files.step.document.render_step` and add BREP builder in `cady.files.step.brep`
6. Add tests
7. Run import boundary tests

### Adding an ops function

- Accept NumPy arrays, array-like tuples, and scalars
- **Do not** import or accept domain objects (no `Shape2D`, `Shape3D`, `Vec2`, `Vec3` as parameters)
- If a domain method needs it, that method unpacks fields and passes primitives

### Adding a numeric type

- Frozen dataclass with NumPy array fields
- Validate in `__post_init__` using `as_points2`, `as_points3`, `as_faces`, etc.
- Provide `.transformed(transform)` method accepting `Transform2`/`Transform3`
- Provide `.bounds()` returning `(min_array, max_array)` tuple

## Testing

### Run gates

```bash
.venv/bin/pytest -q                         # all tests
.venv/bin/pyright src/cady                   # type checking (strict mode)
.venv/bin/ruff check src/cady tests          # linting
```

### Test layout

- `tests/domain/` — domain object construction, bounds, to_array
- `tests/geom/` — transforms, tessellation, triangulation
- `tests/numeric/` — numeric types, validation, mesh operations
- `tests/model/` — Model/Part/Assembly/Drawing2D integration
- `tests/write/` — DXF/STL/STEP output golden-file tests
- `tests/read/` — STEP read tests
- `tests/scene/` — DxfDrawing scene-level tests (bounds, headers, dims)
- `tests/examples/` — end-to-end example script regression tests
- `tests/conventions/` — import boundary and stdlib-only enforcement tests
- `tests/visualisation/` — plotting import smoke tests
- `tests/errors/` — error class behavior tests

### Key conventions

- `PYTHONPATH=src` is required for running scripts
- Conftest provides `run_pyright(path)` helper and `import_env` fixture
- Golden files live in `tests/write/goldens/`
- Temporary output uses `.dxf.tmp` / `.stl.tmp` patterns (gitignored)

## File format support

| Format | Write | Read | Notes |
|--------|-------|------|-------|
| DXF R2018 | Full (lines, polylines, circles, arcs, text, hatch, blocks, dimensions) | No | Zero audit errors on `production_plate.dxf` |
| STL binary | Full | No | Generated from Shape3D tessellation |
| STL ASCII | Full | No | Same data, human-readable |
| STEP AP214 | `Prism`, `Extrusion` | Elementary surfaces only | `Revolution` and `Sphere` not yet supported for STEP export |

## Public API

Top-level re-exports from `cady`:

- Factories: `arc`, `circle`, `line`, `polyline`, `prism`, `rectangle`, `sphere`, `spline`
- Domain: `Vec2`, `Vec3`, `Shape2D`, `Shape3D`, `Line`, `Arc`, `Circle`, `Rectangle`, `Polyline`, `Spline`, `Path`, `Sphere`, `Prism`, `Extrusion`, `Revolution`, `Model`, `Part`, `Assembly`, `Drawing2D`, `DxfDrawing`, `StlMesh`, `Layer`, `ModelLayer`, `ModelMetadata`, `DimStyle`, `AngularDimensionEntity`
- Errors: `CadError`, `SceneError`, `WriteError`
- Ops: `midpoint`, `offset_point`, `perpendicular`
- STEP read: `ExtrudedMember`, `ExtrudedSection`, `extract_members_from_faces`

## Plans

Design documents live in `.plans/`:

- `.plans/files-api/` — file I/O module design
- `.plans/plotting-visualisation/` — visualisation layer design

## Visualisation (optional)

Install: `[project.optional-dependencies] visualisation` brings in matplotlib and pyvista.

Key functions:

- `plot_shape2d(shape, tolerance)` — 2D matplotlib plot
- `view_shape3d(shape, tolerance, backend)` — 3D view (matplotlib or pyvista)
- `view_model(model, tolerance, backend)` — 3D model view

These live in `cady.visualisation` and are never imported by core modules.
