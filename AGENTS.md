# cady — Agent Context

cady is a small native CAD geometry package for building format-blind geometry,
emitting DXF R2018, binary/ASCII STL, or AP214 STEP, and extracting elementary
surface data from STEP files.

## Principles

1. **Semantic > numeric.** Keep authoring geometry as domain objects (`Line2`,
   `Circle2`, `Profile2`, `Body3`). Convert with `.to_array(tolerance=1e-3)`
   or `.to_mesh(tolerance=1e-3)` only at calculation boundaries.
2. **Domain is import-light.** Authoring packages (`geometry2`, `geometry3`,
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
cady.geometry2   2D curves, closed curves, profiles, and factories
cady.geometry3   bodies, faces, frames, meshes, wireframes, features, and primitives
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
| `geometry2`, `geometry3`, `drawing`, `product`, `view` must not import `cady.domain` | `test_import_boundaries.py::test_new_value_packages_do_not_import_legacy_domain` |
| `cady.numeric` must not import `cady.domain` or any authoring package | `test_import_boundaries.py::test_numeric_does_not_import_domain_or_authoring_packages` |
| `cady.ops` must not import `cady.domain` or any authoring package | `test_import_boundaries.py::test_ops_do_not_import_domain_or_authoring_packages` |
| `cady.files` must not import `numpy` or viewer backend modules at module scope | `test_import_boundaries.py::test_files_do_not_import_viewer_or_numpy_at_module_scope` |
| Runtime imports limited to `cady`, `numpy`, `steputils` | `test_stdlib_only.py` |
| Old names (`DxfDrawing`, `Model`, `Prism`, `Extrusion`, `Revolution`, `Sphere`, `Rectangle`, `Shape2`, `Shape3`, `StlMesh`, `SceneError`) must not be exported | `test_public_api_removed.py` |

The intended conversion boundary:

```text
domain object  →  .to_array(tolerance=1e-3)   →  numeric arrays
domain object  →  .to_mesh(tolerance=1e-3)    →  Mesh3 / ArrayMesh3
domain object  →  dxf/stl/step.write(...)     →  files
```

### Key files

| File | Purpose |
|------|---------|
| `src/cady/__init__.py` | Public API re-exports |
| `src/cady/vec.py` | `Vec2`, `Vec3` frozen dataclasses |
| `src/cady/errors.py` | Exception hierarchy (`CadError`, `GeometryError`, `DrawingError`, `ProductError`, `ViewError`, `ReadError`, `WriteError`) |
| `src/cady/geometry2/curves.py` | `Line2`, `Arc2`, `Spline2`, `Polyline2`, `ClosedPolyline2`, `Circle2`, `Ellipse2`, protocol ABCs |
| `src/cady/geometry2/factories.py` | `line2()`, `arc2()`, `circle2()`, `polyline2()`, `profile_rectangle()`, `profile_circle()` |
| `src/cady/geometry2/profile.py` | `Profile2` filled region (outer boundary + holes) |
| `src/cady/geometry3/body.py` | `Body3` — editable solid with feature history |
| `src/cady/geometry3/frame.py` | `Frame3` — 3D coordinate frame |
| `src/cady/geometry3/face.py` | `Face3` — `Profile2` placed in a `Frame3` |
| `src/cady/geometry3/mesh.py` | `Mesh3` — semantic triangle mesh |
| `src/cady/geometry3/wireframe.py` | `Wireframe3` — edge-only wireframe (vertices + edges, no faces) |
| `src/cady/geometry3/features.py` | Feature records (`ExtrudeFeature`, `RevolveFeature`, `BooleanFeature`, `FilletFeature`, `ChamferFeature`, `PrimitiveFeature`) |
| `src/cady/geometry3/factories.py` | `box()`, `cylinder()`, `sphere()` convenience constructors |
| `src/cady/operations/_mesh_builders.py` | Feature-to-triangles evaluators |
| `src/cady/drawing/document.py` | `Drawing2` — 2D drafting document |
| `src/cady/drawing/layers.py` | `Layer`, `DrawingEntity` |
| `src/cady/drawing/entities.py` | `Text2`, `Hatch2`, `Insert2`, `BlockDefinition` |
| `src/cady/drawing/dimensions.py` | `DimStyle`, `LinearDimension2`, `AlignedDimension2`, `RadiusDimension2`, `DiameterDimension2`, `AngularDimension2` |
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
| `src/cady/numeric/mesh3.py` | `ArrayMesh3`, `ArrayPolyline3` |
| `src/cady/numeric/paths2.py` | `ArrayPolyline2`, `ArrayPolygon2` |
| `src/cady/numeric/curves2.py` | `ArrayBezierSpline2` |
| `src/cady/numeric/transform.py` | `Transform2`, `Transform3`, `Pose3` |
| `src/cady/numeric/validation.py` | `as_points2`, `as_points3`, `as_faces`, `as_matrix3`, `as_matrix4` |
| `src/cady/numeric/bounds.py` | `bounds2`, `bounds3` |
| `src/cady/numeric/types.py` | NumPy type aliases |
| `src/cady/ops/curves2.py` | Curve discretisation algorithms |
| `src/cady/ops/polygons2.py` | Polygon operations (offset, boolean hints) |
| `src/cady/ops/mesh_cut.py` | `cut_mesh_by_plane`, `close_planar_cap`, `close_boundary` |
| `src/cady/ops/meshes3.py` | Mesh-level operations |
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

1. Subclass `Curve2` or `ClosedCurve2` in `cady.geometry2.curves` (frozen dataclass)
2. Implement `bounds()`, `points()`, `close()`, `_transform2()`, `to_array()`
3. Add factory to `cady.geometry2.factories`
4. Re-export from `cady.geometry2.__init__` and `cady.__init__`
5. Add tests under `tests/geometry2/`
6. Run import boundary tests

### Adding a 3D shape / feature

1. Add feature record to `cady.geometry3.features`
2. Add evaluation path to `cady.operations._mesh_builders`
3. Wire into `Body3` in `cady.geometry3.body`
4. Re-export from `cady.geometry3.__init__` and `cady.__init__`
5. If STEP export is desired, add BREP builder in `cady.files.step`
6. Add tests under `tests/geometry3/`
7. Run import boundary tests

### Adding an ops function

- Accept NumPy arrays, array-like tuples, and scalars
- **Do not** import or accept domain objects (no `Body3`, `Mesh3`, `Profile2`, `Vec2`, `Vec3` as parameters)
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

- `tests/geometry2/` — curve/profile construction, bounds, to_array
- `tests/geometry3/` — body, face, frame, mesh, wireframe tests
- `tests/drawing/` — Drawing2, dimensions, layers
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
| DXF R2018 | `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `TEXT` from `Drawing2` | 2D entities, `3DFACE` meshes, 3D polyline wires | Hatches, blocks, inserts, and dimensions modeled but not yet emitted |
| STL binary | Full | No | From `Mesh3`, `ArrayMesh3`, `Body3`, `Part`, `Assembly`, or `Document` |
| STL ASCII | Full | No | Same data, human-readable |
| STEP AP214 | Mesh-oriented (points + `POLY_LOOP` faces) | Elementary surfaces and extruded member extraction | True B-rep solid export not yet implemented |

## Public API

Top-level re-exports from `cady`:

- Factories: `line2`, `arc2`, `circle2`, `polyline2`, `profile_rectangle`, `profile_circle`, `box`, `cylinder`, `sphere`
- 2D geometry: `Line2`, `Arc2`, `Spline2`, `Polyline2`, `ClosedPolyline2`, `Circle2`, `Ellipse2`, `Curve2`, `ClosedCurve2`, `Profile2`
- 3D geometry: `Body3`, `Face3`, `Frame3`, `Mesh3`, `Wireframe3`
- Drawing: `Drawing2`, `DrawingEntity`, `Layer`, `Text2`, `Hatch2`, `Insert2`, `BlockDefinition`, `DimStyle`, `LinearDimension2`, `AlignedDimension2`, `RadiusDimension2`, `DiameterDimension2`, `AngularDimension2`
- Product: `Part`, `PartInstance`, `Assembly`, `AssemblyInstance`, `Material`
- View: `Scene`, `SceneObject`, `Camera`, `Light`, `AmbientLight`, `DirectionalLight`, `PointLight`, `DisplayStyle`
- Document: `Document`
- Vectors: `Vec2`, `Vec3`, `Pose3`
- Errors: `CadError`, `GeometryError`, `DrawingError`, `ProductError`, `ViewError`, `ReadError`, `WriteError`
- Modules: `cady.files.dxf`, `cady.files.stl`, `cady.files.step`

## Plans

Design documents live in `.plans/`:

- `.plans/polyline-to-mesh/` — closed polyline to mesh conversion

## Viewing (optional)

Install: `[project.optional-dependencies] view` brings in pyqt6 and vispy.
`[project.optional-dependencies] all` includes plotting and view extras.

Key functions in `cady.view`:

- `view_target(target, *, tolerance, backend)` — view a `Body3`, `Part`, `Assembly`, `Mesh3`, `Wireframe3`, or `Drawing2`
- `view_scene(scene, *, backend)` — view a `Scene` with its cameras, lights, and display styles
- `view_mesh(mesh, *, backend)` — view an `ArrayMesh3`
- `view_meshes(meshes, *, backend)` — view multiple `ArrayMesh3` values
- `view_lines(vertices, edges, *, backend)` — view edge-only wireframe data
- `prepare_scene(scene)` — prepare a `Scene` for rendering, returns `PreparedScene`
- `scene_from_target(target, *, name)` — create a `Scene` from any viewable target

The viewer helpers live in `cady.view`; backend GUI packages are imported only
when a viewer function is launched.
