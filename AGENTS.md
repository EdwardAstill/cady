# cady — Agent Context

cady is a small native CAD geometry package for building format-blind geometry,
emitting DXF R2018, binary/ASCII STL, or AP214 STEP, and extracting elementary
surface data from STEP files.

## Principles

1. **Semantic > numeric.** Keep authoring geometry as domain objects (`Line2D`,
   `Circle2D`, `Profile2D`, `Body3D`). Convert with `.to_array(tolerance=1e-3)`
   or `.to_mesh(tolerance=1e-3)` only at calculation boundaries.
2. **Domain is import-light.** Authoring packages (`geometry2d`, `geometry3d`,
   `drawing`, `product`) must not import `numpy`, `matplotlib`, `pyvista`,
   `vispy`, or viewer backend modules at module scope. Validate with
   `tests/conventions/test_import_boundaries.py` and
   `tests/conventions/test_stdlib_only.py`.
3. **Immutable domain objects.** All shapes, vectors, and metadata are frozen
   dataclasses (`frozen=True`). Transforms return new instances; never mutate.
4. **Tolerance is explicit.** Every `to_array(...)`, `.to_mesh(...)`, and export
   function accepts `tolerance` as a keyword argument. No hidden defaults.
5. **No external deps at runtime.** Runtime imports are limited to `cady`,
   `numpy`, and `steputils`. `matplotlib`, `vispy`, and `pyvista` are optional
   extras gated behind `[view]` and `[all]`. Enforced by
   `tests/conventions/test_stdlib_only.py`.
6. **Layers are named, not numbered.** Drawings assign entities to named layers
   with color and linetype. DXF writers map these to DXF layer tables.

## Architecture

```text
cady.geometry2d   2D curves, closed curves, profiles, and factories
cady.geometry3d   bodies, faces, frames, meshes, wireframes, features, and primitives
cady.drawing      drawing documents, layers, text, hatches, blocks, dimensions
cady.product      parts, assemblies, materials, and assembly flattening
cady.view         scenes, cameras, lights, display styles, optional viewers
cady.document     optional top-level registry
cady.numeric      NumPy-backed evaluated arrays and transforms
cady.ops          object-agnostic geometry algorithms
cady.files        DXF, STL, and STEP facades
cady.errors       shared exception hierarchy
cady.vec          Vec2, Vec3 immutable vector types
```

### Dependency rules (enforced by CI)

| Rule | Test |
|------|------|
| `cady.domain` and `cady.build` packages must not exist | `test_import_boundaries.py::test_legacy_domain_and_build_packages_are_removed` |
| `geometry2d`, `geometry3d`, `drawing`, `product`, `view` must not import `cady.domain` | `test_import_boundaries.py::test_new_value_packages_do_not_import_legacy_domain` |
| `cady.numeric` must not import `cady.domain` or any authoring package | `test_import_boundaries.py::test_numeric_does_not_import_domain_or_authoring_packages` |
| `cady.ops` must not import `cady.domain` or any authoring package | `test_import_boundaries.py::test_ops_do_not_import_domain_or_authoring_packages` |
| `cady.files` must not import `numpy` or viewer backend modules at module scope | `test_import_boundaries.py::test_files_do_not_import_viewer_or_numpy_at_module_scope` |
| Runtime imports limited to `cady`, `numpy`, `steputils` | `test_stdlib_only.py` |
| Old names (`DxfDrawing`, `Model`, `Prism`, `Extrusion`, `Revolution`, `Sphere`, `Rectangle`, `Shape2D`, `Shape3D`, `StlMesh`, `SceneError`) must not be exported | `test_public_api_removed.py` |

The intended conversion boundary:

```text
domain object  →  .to_array(tolerance=1e-3)   →  numeric arrays
domain object  →  .to_mesh(tolerance=1e-3)    →  Mesh3D / ArrayMesh3
domain object  →  dxf/stl/step.write(...)     →  files
```

### Key files

| File | Purpose |
|------|---------|
| `src/cady/__init__.py` | Public API re-exports |
| `src/cady/vec.py` | `Vec2`, `Vec3` frozen dataclasses |
| `src/cady/errors.py` | Exception hierarchy (`CadError`, `GeometryError`, `DrawingError`, `ProductError`, `ViewError`, `ReadError`, `WriteError`) |
| `src/cady/geometry2d/curves.py` | `Line2D`, `Arc2D`, `Spline2D`, `Polyline2D`, `ClosedPolyline2D`, `Circle2D`, `Ellipse2D`, protocol ABCs |
| `src/cady/geometry2d/factories.py` | `line2d()`, `arc2d()`, `circle2d()`, `polyline2d()`, `profile_rectangle()`, `profile_circle()` |
| `src/cady/geometry2d/profile.py` | `Profile2D` filled region (outer boundary + holes) |
| `src/cady/geometry3d/body.py` | `Body3D` — editable solid with feature history |
| `src/cady/geometry3d/frame.py` | `Frame3D` — 3D coordinate frame |
| `src/cady/geometry3d/face.py` | `Face3D` — `Profile2D` placed in a `Frame3D` |
| `src/cady/geometry3d/mesh.py` | `Mesh3D` — semantic triangle mesh |
| `src/cady/geometry3d/wireframe.py` | `Wireframe3D` — edge-only wireframe (vertices + edges, no faces) |
| `src/cady/geometry3d/features.py` | Feature records (`ExtrudeFeature`, `RevolveFeature`, `BooleanFeature`, `FilletFeature`, `ChamferFeature`, `PrimitiveFeature`) |
| `src/cady/geometry3d/factories.py` | `box()`, `cylinder()`, `sphere()` convenience constructors |
| `src/cady/geometry3d/_mesh_builders.py` | Feature-to-triangles evaluators |
| `src/cady/drawing/document.py` | `Drawing2D` — 2D drafting document |
| `src/cady/drawing/layers.py` | `Layer`, `DrawingEntity` |
| `src/cady/drawing/entities.py` | `Text2D`, `Hatch2D`, `Insert2D`, `BlockDefinition` |
| `src/cady/drawing/dimensions.py` | `DimStyle`, `LinearDimension2D`, `AlignedDimension2D`, `RadiusDimension2D`, `DiameterDimension2D`, `AngularDimension2D` |
| `src/cady/drawing/_geometry.py` | Drawing geometry helpers |
| `src/cady/product/part.py` | `Part` — named manufacturable item |
| `src/cady/product/assembly.py` | `Assembly` — tree of placed parts and subassemblies |
| `src/cady/product/flatten.py` | Assembly flattening to `FlattenedPart` records |
| `src/cady/product/material.py` | `Material` |
| `src/cady/view/scene.py` | `Scene` — backend-independent view description |
| `src/cady/view/camera.py` | `Camera` — perspective/orthographic camera |
| `src/cady/view/light.py` | `Light` protocol, `AmbientLight`, `DirectionalLight`, `PointLight` |
| `src/cady/view/style.py` | `DisplayStyle` |
| `src/cady/view/open_view.py` | `SceneObject` — target reference with pose and visibility |
| `src/cady/view/mesh_buffers.py` | Mesh-to-GPU-buffer conversion |
| `src/cady/view/vispy_viewer.py` | Vispy-based 3D viewer (`view_scene`, `view_target`, `view_mesh`, `view_meshes`, `view_lines`, `prepare_scene`) |
| `src/cady/document.py` | `Document` — optional registry of named drawings, parts, assemblies, scenes |
| `src/cady/numeric/mesh3d.py` | `ArrayMesh3`, `ArrayPolyline3` |
| `src/cady/numeric/paths2d.py` | `ArrayPolyline2`, `ArrayPolygon2` |
| `src/cady/numeric/curves2d.py` | `ArrayBezierSpline2` |
| `src/cady/numeric/transform.py` | `Transform2`, `Transform3`, `Pose3` |
| `src/cady/numeric/validation.py` | `as_points2`, `as_points3`, `as_faces`, `as_matrix3`, `as_matrix4` |
| `src/cady/numeric/bounds.py` | `bounds2`, `bounds3` |
| `src/cady/numeric/types.py` | NumPy type aliases |
| `src/cady/ops/curves2d.py` | Curve discretisation algorithms |
| `src/cady/ops/polygons2d.py` | Polygon operations (offset, boolean hints) |
| `src/cady/ops/mesh_cut.py` | `cut_mesh_by_plane`, `close_planar_cap`, `close_boundary` |
| `src/cady/ops/meshes3d.py` | Mesh-level operations |
| `src/cady/ops/linesplan.py` | Linesplan wireframe meshing |
| `src/cady/ops/point_transforms.py` | Point-level transforms |
| `src/cady/ops/profiles.py` | Profile geometry helpers |
| `src/cady/ops/triangulation.py` | Polygon triangulation |
| `src/cady/files/dxf/__init__.py` | DXF write (`write`, `render`) and read (`read`, `read_drawing`, `read_mesh`, `read_wireframe`) |
| `src/cady/files/stl/ascii.py` | ASCII STL writer |
| `src/cady/files/stl/binary.py` | Binary STL writer |
| `src/cady/files/step/__init__.py` | STEP write (`write`, `render`) and read (`read_faces`, `read_members`, `read_step`) |
| `src/cady/files/step/faces.py` | STEP face parser |
| `src/cady/files/step/members.py` | `extract_members_from_faces` — structural member extraction |
| `src/cady/files/step/ids.py` | `IdAllocator` — STEP entity ID management |

## Module boundaries when editing

### Adding a 2D shape

1. Subclass `Curve2D` or `ClosedCurve2D` in `cady.geometry2d.curves` (frozen dataclass)
2. Implement `bounds()`, `points()`, `close()`, `_transform2()`, `to_array()`
3. Add factory to `cady.geometry2d.factories`
4. Re-export from `cady.geometry2d.__init__` and `cady.__init__`
5. Add tests under `tests/geometry2d/`
6. Run import boundary tests

### Adding a 3D shape / feature

1. Add feature record to `cady.geometry3d.features`
2. Add evaluation path to `cady.geometry3d._mesh_builders`
3. Wire into `Body3D` in `cady.geometry3d.body`
4. Re-export from `cady.geometry3d.__init__` and `cady.__init__`
5. If STEP export is desired, add BREP builder in `cady.files.step`
6. Add tests under `tests/geometry3d/`
7. Run import boundary tests

### Adding an ops function

- Accept NumPy arrays, array-like tuples, and scalars
- **Do not** import or accept domain objects (no `Body3D`, `Mesh3D`, `Profile2D`, `Vec2`, `Vec3` as parameters)
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

- `tests/geometry2d/` — curve/profile construction, bounds, to_array
- `tests/geometry3d/` — body, face, frame, mesh, wireframe tests
- `tests/drawing/` — Drawing2D, dimensions, layers
- `tests/product/` — Part, Assembly, flattening
- `tests/view/` — Camera, lights, Scene, object view methods, viewer smoke tests
- `tests/document/` — Document registry
- `tests/numeric/` — numeric types, validation, mesh operations, transforms
- `tests/files/` — DXF/STL/STEP I/O tests
- `tests/examples/` — end-to-end example script regression tests
- `tests/conventions/` — import boundary, stdlib-only, and removed-API enforcement tests
- `tests/errors/` — error class behavior tests

### Key conventions

- `PYTHONPATH=src` is required for running scripts
- Conftest provides `run_pyright(path)` helper and `import_env` fixture
- Golden files live in `tests/write/goldens/`
- Temporary output uses `.dxf.tmp` / `.stl.tmp` patterns (gitignored)

## File format support

| Format | Write | Read | Notes |
|--------|-------|------|-------|
| DXF R2018 | `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `TEXT` from `Drawing2D` | 2D entities, `3DFACE` meshes, 3D polyline wires | Hatches, blocks, inserts, and dimensions modeled but not yet emitted |
| STL binary | Full | No | From `Mesh3D`, `ArrayMesh3`, `Body3D`, `Part`, `Assembly`, or `Document` |
| STL ASCII | Full | No | Same data, human-readable |
| STEP AP214 | Mesh-oriented (points + `POLY_LOOP` faces) | Elementary surfaces and extruded member extraction | True B-rep solid export not yet implemented |

## Public API

Top-level re-exports from `cady`:

- Factories: `line2d`, `arc2d`, `circle2d`, `polyline2d`, `profile_rectangle`, `profile_circle`, `box`, `cylinder`, `sphere`
- 2D geometry: `Line2D`, `Arc2D`, `Spline2D`, `Polyline2D`, `ClosedPolyline2D`, `Circle2D`, `Ellipse2D`, `Curve2D`, `ClosedCurve2D`, `Profile2D`
- 3D geometry: `Body3D`, `Face3D`, `Frame3D`, `Mesh3D`, `Wireframe3D`
- Drawing: `Drawing2D`, `DrawingEntity`, `Layer`, `Text2D`, `Hatch2D`, `Insert2D`, `BlockDefinition`, `DimStyle`, `LinearDimension2D`, `AlignedDimension2D`, `RadiusDimension2D`, `DiameterDimension2D`, `AngularDimension2D`
- Product: `Part`, `PartInstance`, `Assembly`, `AssemblyInstance`, `Material`
- View: `Scene`, `SceneObject`, `Camera`, `Light`, `AmbientLight`, `DirectionalLight`, `PointLight`, `DisplayStyle`
- Document: `Document`
- Vectors: `Vec2`, `Vec3`, `Pose3D`
- Errors: `CadError`, `GeometryError`, `DrawingError`, `ProductError`, `ViewError`, `ReadError`, `WriteError`
- Modules: `cady.files.dxf`, `cady.files.stl`, `cady.files.step`

## Plans

Design documents live in `.plans/`:

- `.plans/linesplan-wireframe-meshing/` — linesplan wireframe mesh generation from 2D station/waterline/buttock curves

## Viewing (optional)

Install: `[project.optional-dependencies] view` brings in pyqt6 and vispy.
`[project.optional-dependencies] all` includes plotting and view extras.

Key functions in `cady.view`:

- `view_target(target, *, tolerance, backend)` — view a `Body3D`, `Part`, `Assembly`, `Mesh3D`, `Wireframe3D`, or `Drawing2D`
- `view_scene(scene, *, backend)` — view a `Scene` with its cameras, lights, and display styles
- `view_mesh(mesh, *, backend)` — view an `ArrayMesh3`
- `view_meshes(meshes, *, backend)` — view multiple `ArrayMesh3` values
- `view_lines(vertices, edges, *, backend)` — view edge-only wireframe data
- `prepare_scene(scene)` — prepare a `Scene` for rendering, returns `PreparedScene`
- `scene_from_target(target, *, name)` — create a `Scene` from any viewable target

The viewer helpers live in `cady.view`; backend GUI packages are imported only
when a viewer function is launched.
