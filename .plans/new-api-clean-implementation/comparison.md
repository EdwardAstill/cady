# Current Versus Target

## Optimal

These parts can mostly stay, with changed call sites or names:

- `src/cady/numeric/*`: array-backed evaluated geometry, transforms, bounds, and
  validation already match the target evaluation layer.
- `src/cady/ops/curves2d.py`, `polygons2d.py`, `meshes3d.py`,
  `triangulation.py`, `mesh_cut.py`, `point_transforms.py`: these are mostly
  primitive numeric algorithms and should remain the backend for evaluation.
- `src/cady/files/dxf/parser.py`: the group-code parser is format-level and can
  be reused unchanged.
- `src/cady/files/dxf/emit.py`, `codes.py`, and most of the DXF section/table
  rendering machinery: useful writer internals once their input contract moves
  from `DxfDrawing`/`Shape2D` to `Drawing2D`/drawing entities.
- `src/cady/files/stl/ascii.py` and `binary.py`: low-level STL emitters should
  stay and accept triangle lists from the new mesh evaluation layer.
- `src/cady/files/step/ids.py`, `faces.py`, `members.py`: STEP ID allocation and
  read/extraction code can remain, with package exports updated.

## Close

These are directionally right but need significant restructuring:

- `src/cady/domain/drawing.py`: contains useful layer, text, hatch, block, and
  dimension concepts, but the public type must become `Drawing2D`, not
  `DxfDrawing`, and it must be immutable/value-oriented rather than a mutable
  DXF builder.
- `src/cady/domain/mesh.py`: `Face3D`, `Polyline3D`, and `FacetedMesh` should
  become `Face3D`, `Curve3D`/`Polyline3D`, and `Mesh3D`. `StlMesh` should move
  out of domain and become a file writer detail or disappear.
- `src/cady/domain/vec.py`: keep `Vec2` and `Vec3` or rename them to
  `Point2D`/`Vector2D` and `Point3D`/`Vector3D` aliases. The clean API can
  still use simple coordinate tuples publicly.
- `src/cady/files/dxf/reader.py`: already reads 2D DXF into a drawing-like
  object and 3D faces/polyfaces into a faceted mesh. It should return
  `Drawing2D`, `Mesh3D`, and a `DxfImportResult`.
- `src/cady/files/step/brep.py` and `document.py`: B-rep construction for boxes
  and extrusions can survive, but must consume `Body3D`/features through a
  conversion layer rather than old `Prism`/`Extrusion` classes.
- `src/cady/visualisation/*` and `src/cady/plotting/*`: should become adapters
  that consume `Scene` and default-scene wrappers around direct objects.

## Different

These should be replaced rather than migrated compatibly:

- `src/cady/domain/base.py`: `Shape2D`/`Shape3D` are too broad. Replace with
  explicit `Curve2D`, `ClosedCurve2D`, `Profile2D`, `Body3D`, and evaluated
  `Mesh3D` concepts.
- `src/cady/domain/shapes2d.py`: old names and hierarchy mix open curves,
  closed boundaries, profiles, holes, and factories. Replace with
  `geometry2d` modules.
- `src/cady/domain/shapes3d.py`: old primitive classes should become
  `Body3D` features and factories, not public `Prism`/`Sphere` shape classes.
- `src/cady/domain/model.py`: `Model` must be removed. Its useful concerns
  split into `Drawing2D`, `Part`, `Assembly`, and optional `Document`.
- `src/cady/domain/part.py` and `assembly.py`: currently re-export wrappers.
  Replace with real `cady.product` modules.
- `src/cady/build/factories.py`: factory API should produce new concepts:
  curves, profiles, bodies, parts, scenes; no legacy `rectangle` core class or
  `prism` class.
- `src/cady/ops/tessellate.py` and `transforms.py`: currently import old domain
  types. Split into numeric primitive functions and domain evaluation methods
  so `ops` no longer imports domain.
- `src/cady/files/dxf/__init__.py`, `stl/__init__.py`, `step/__init__.py`:
  replace `write_model` and legacy overloads with direct `read`, `write`,
  `render`, `read_drawing`, `read_mesh`, and object-specific dispatch.
- `src/cady/__init__.py` and `src/cady/domain/__init__.py`: replace public
  exports wholesale with the new API. Do not export removed names.

## Dead

Delete or stop exposing these as public API:

- `Model`, `ModelLayer`, `ModelMetadata`.
- `DxfDrawing` as a public object.
- `StlMesh` as a public domain object.
- `Shape2D`, `Shape3D`.
- `Rectangle` as a core geometry class.
- `Prism`, `Sphere`, `Extrusion`, `Revolution` as public primitive shape
  classes. Their behavior should be represented as `Body3D` features/factories.
- `write_model` file facade functions.
- Tests whose main purpose is legacy compatibility with `Model`, `DxfDrawing`,
  `StlMesh`, or old shape names.

## Practical Adjustment To Ideal

Keep `Vec2` and `Vec3` internally for now unless renaming them proves cheap.
The public API can still accept coordinate tuples and expose `Point2D`/`Point3D`
aliases later. Renaming every vector reference is low-value compared with
replacing the object model.

Keep DXF render internals and STEP/STL emitters initially. The clean
implementation should be a clean public/domain rewrite, not a rewrite of
serialisation mechanics that are already covered by tests.

For the first pass, STEP assembly export should flatten assemblies into placed
part solids. Preserving STEP product structure is explicitly future work.
