# New API Clean Implementation Spec

## Goal

Replace the existing cady public API and source structure with the new object
model. No legacy API, compatibility wrappers, deprecated aliases, or old facade
functions are required.

The implementation should make these concepts first-class:

- 2D curves and profiles;
- `Drawing2D` as the 2D drafting/document object;
- 3D frames, faces, bodies, and meshes;
- `Part` and `Assembly` as product structure;
- `Scene`, `Camera`, and `Light` as viewing state;
- optional `Document` as a project-level registry.

## Non-Goals

- Do not preserve `Model`, `DxfDrawing`, `StlMesh`, `Shape2D`, `Shape3D`,
  `Rectangle`, `Prism`, `Sphere`, `Extrusion`, or `Revolution` as public API.
- Do not keep `write_model` functions.
- Do not implement full 3D DXF-to-Body conversion yet.
- Do not preserve STEP assembly product structure yet.
- Do not add new runtime dependencies beyond the current allowed dependency
  rules.

## Drawing Objects In The New API

`Drawing2D` is the canonical object for 2D CAD drawings. It is a peer of
`Part`, `Assembly`, `Scene`, and `Document`, not a child of `Model`.

Use it when:

- authoring or writing DXF;
- reading 2D DXF files;
- managing layers, text, hatches, blocks, inserts, and dimensions;
- viewing 2D drafting content in a scene.

`Drawing2D` owns drafting-specific metadata that does not belong on bare curves:

```text
Drawing2D
  name
  units
  layers
  entities
  blocks
  dim_styles
  header variables
  metadata
```

Drawing geometry is stored as drawing entities:

```text
DrawingEntity
  geometry -> Curve2D | ClosedCurve2D | Profile2D
  layer -> str
  style -> optional entity style
```

Text, hatch, insert, and dimensions are their own drawing entity classes because
they have drafting behavior beyond pure geometry.

DXF import behavior:

- If the DXF contains 2D drafting entities, `dxf.read_drawing(path)` returns a
  `Drawing2D`.
- If the DXF contains supported faceted 3D entities, `dxf.read_mesh(path)`
  returns a `Mesh3D`.
- `dxf.read(path)` returns a `DxfImportResult` with optional `drawing`, meshes,
  wires, and skipped entity reports.
- Future DXF recognition can promote closed 2D loops to `Profile2D` and 3D
  entities to `Body3D`, `Part`, or `Assembly`, but this is outside the first
  pass.

## Public API

Top-level `cady` should export the core authoring objects:

```python
from cady import (
    Arc2D,
    Assembly,
    Body3D,
    Camera,
    Circle2D,
    ClosedPolyline2D,
    Curve2D,
    DirectionalLight,
    DisplayStyle,
    Document,
    Drawing2D,
    Ellipse2D,
    Face3D,
    Frame3D,
    Layer,
    Light,
    Line2D,
    Mesh3D,
    Part,
    PointLight,
    Polyline2D,
    Pose3D,
    Profile2D,
    Scene,
    Spline2D,
    Vec2,
    Vec3,
)
```

Top-level factory functions should be explicit and map to new concepts:

```python
line2d(...)
arc2d(...)
circle2d(...)
polyline2d(...)
profile_rectangle(...)
profile_circle(...)
box(...)
cylinder(...)
sphere(...)
scene(...)
```

Short aliases may exist only if they point to new concepts and do not imply the
old class model. For example, `box(...) -> Body3D` is fine; `prism(...) ->
Prism` is not.

## Module Structure

Target source tree:

```text
src/cady/
  __init__.py
  errors.py
  geometry2d/
    __init__.py
    curves.py
    profile.py
    factories.py
  geometry3d/
    __init__.py
    frame.py
    face.py
    body.py
    features.py
    mesh.py
    factories.py
  drawing/
    __init__.py
    entities.py
    layers.py
    dimensions.py
    blocks.py
    document.py
  product/
    __init__.py
    material.py
    part.py
    assembly.py
    flatten.py
  view/
    __init__.py
    camera.py
    light.py
    scene.py
    style.py
  document.py
  numeric/
    existing numeric modules
  ops/
    existing primitive numeric modules
    evaluate2d.py
    evaluate3d.py
  files/
    dxf/
    stl/
    step/
  visualisation/
    existing adapters updated for Scene
```

Remove or replace:

```text
src/cady/domain/base.py
src/cady/domain/shapes2d.py
src/cady/domain/shapes3d.py
src/cady/domain/model.py
src/cady/domain/drawing.py
src/cady/domain/mesh.py
src/cady/domain/part.py
src/cady/domain/assembly.py
src/cady/build/factories.py
```

The `cady.domain` and `cady.build` packages can be deleted entirely. If leaving
empty packages would avoid packaging friction, they must not re-export legacy
names.

## Core Type Contracts

All authoring/value objects should be frozen dataclasses with slots.

Mutating builder-style methods should return new instances:

```python
drawing = Drawing2D("front").add(line, layer="GEOM")
part = Part("plate").with_body(body)
assembly = Assembly("assy").add(part, name="plate")
scene = Scene.from_target(assembly).with_camera(camera)
```

Use tuple fields, not mutable lists/dicts, in domain/view/product objects.

Validation errors:

- invalid geometry: `GeometryError`;
- invalid drawing composition: `DrawingError`;
- invalid part/assembly structure: `ProductError`;
- invalid scene/camera/light: `ViewError`;
- import failure: `ReadError`;
- export failure: `WriteError`.

## Evaluation Boundaries

Semantic objects evaluate only when asked:

```python
curve.to_array(tolerance=...)
profile.to_array(tolerance=...)
body.to_mesh(tolerance=...)
part.to_mesh(tolerance=...)
assembly.to_mesh(tolerance=...)
drawing.to_arrays(tolerance=...)
```

`tolerance` must be keyword-only and explicit on all public evaluation/export
paths. Internal helper defaults are allowed only when not exposed publicly and
not controlling discretisation.

## File I/O

DXF:

```python
dxf.read(path) -> DxfImportResult
dxf.read_drawing(path) -> Drawing2D
dxf.read_mesh(path) -> Mesh3D
dxf.render(drawing: Drawing2D, *, tolerance: float) -> str
dxf.write(drawing: Drawing2D, path, *, tolerance: float) -> Drawing2D
```

STL:

```python
stl.write(target: Mesh3D | Body3D | Part | Assembly | Document, path, *, ascii: bool, tolerance: float)
stl.render_ascii(target: Mesh3D | Body3D | Part | Assembly | Document, *, tolerance: float) -> str
```

STEP:

```python
step.write(target: Body3D | Part | Assembly | Document, path) -> object
step.render(target: Body3D | Part | Assembly | Document, *, name: str | None = None) -> str
step.read_faces(path) -> list[StepFace]
step.read_members(path) -> list[ExtrudedMember]
```

No `write_model` functions.

## Import Boundary Rules

Update convention tests to enforce:

- core packages `geometry2d`, `geometry3d`, `drawing`, `product`, `view`, and
  `document` do not import matplotlib, pyvista/vispy, or other optional
  visualisation backends at module scope;
- `numeric` does not import domain/product/view/drawing packages;
- `ops` does not import domain/product/view/drawing packages;
- `files` does not import visualisation backends or NumPy at module scope;
- runtime import allowlist remains stdlib + `cady` + `numpy` + `steputils`,
  with optional plotting/visualisation packages only in optional packages.

## Done Criteria

- Old public names are gone from top-level `cady` and package exports.
- Tests no longer import or assert behavior for `Model`, `DxfDrawing`,
  `StlMesh`, `Shape2D`, `Shape3D`, `Rectangle`, `Prism`, `Sphere`,
  `Extrusion`, or `Revolution`.
- `Drawing2D` can be authored directly and written to DXF.
- 2D DXF can be read into `Drawing2D`.
- Supported 3D DXF faceted/polyface data can be read into `Mesh3D`.
- `Body3D` can represent at least box/cylinder/sphere/extrusion features and
  can evaluate to `Mesh3D`.
- `Part` and nested `Assembly` can flatten to placed meshes.
- `Scene` can wrap a drawing/body/part/assembly/mesh with camera and lights.
- STL writes direct meshes, bodies, parts, assemblies, and supported documents.
- STEP writes supported bodies/parts and flattened assemblies where possible.
- Full gates pass:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```
