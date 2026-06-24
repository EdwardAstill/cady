# API Contract

## Direct Geometry Authoring

```python
from cady import Body3D, Part, Profile2D

profile = Profile2D.rectangle(width=120, height=80)
body = profile.extrude(distance=8)
part = Part("plate").with_body(body)
```

Expected behavior:

- `Profile2D.rectangle(...)` returns a `Profile2D`, not a rectangle shape.
- `Profile2D.extrude(...)` returns a `Body3D`.
- `Part.with_body(...)` returns a new `Part`; the original part is unchanged.
- `body.to_mesh(tolerance=...)` returns `Mesh3D`.

## Drawing Authoring

```python
from cady import Drawing2D, Layer, line2d, profile_rectangle

drawing = (
    Drawing2D("front")
    .add_layer(Layer("PLATE", color=3, linetype="CENTER"))
    .add(profile_rectangle(120, 80), layer="PLATE")
    .add(line2d((0, 0), (120, 80)), layer="CONSTRUCTION")
    .add_text("PLATE", at=(5, 5), height=2.5, layer="TEXT")
)
```

Expected behavior:

- `Drawing2D` is directly constructible.
- Adding geometry creates drawing entities with layer assignment.
- Missing layers may be auto-created with default style or rejected; choose one
  policy during implementation and test it. Recommended first policy:
  auto-create missing layers with default color/linetype.
- `drawing.bounds()` includes geometry, text anchors, hatches, inserts, and
  dimensions.
- `dxf.write(drawing, path, tolerance=...)` writes a DXF R2018 file.

## DXF Import

```python
from cady.files import dxf

drawing = dxf.read_drawing("plate.dxf")
mesh = dxf.read_mesh("faceted.dxf")
result = dxf.read("mixed.dxf")
```

Expected behavior:

- `read_drawing` returns `Drawing2D`.
- `read_mesh` returns a single merged `Mesh3D`.
- `read` returns `DxfImportResult`.
- `DxfImportResult.drawing` is set when 2D drawing entities are present.
- `DxfImportResult.meshes` contains supported 3D faceted/polyface meshes.
- Unsupported 3D ACIS-backed entities are reported in `skipped`, not silently
  turned into bodies.

Initial supported 2D DXF entities:

- `LINE` -> `Line2D`;
- `LWPOLYLINE` -> `Polyline2D` or `ClosedPolyline2D`;
- `CIRCLE` -> `Circle2D`;
- `ARC` -> `Arc2D`;
- `TEXT`/`MTEXT` -> `Text2D`.

Initial supported 3D DXF entities:

- `3DFACE` -> `Mesh3D`;
- 3D `POLYLINE` wire -> `Polyline3D`;
- polyface `POLYLINE` -> `Mesh3D`.

Future promotion:

- closed 2D drawing loops -> `Profile2D`;
- recognised 3D solids/surfaces -> `Body3D`, `Part`, or `Assembly`.

## Product Structure

```python
from cady import Assembly, Body3D, Part, Pose3D

plate = Part("plate").with_body(Body3D.box(width=120, depth=80, height=8))
bolt = Part("bolt").with_body(Body3D.cylinder(radius=4, height=30))

assembly = (
    Assembly("plate_with_bolts")
    .add(plate, name="plate")
    .add(bolt, name="bolt_a", pose=Pose3D.at(20, 20, 8))
    .add(bolt, name="bolt_b", pose=Pose3D.at(100, 20, 8))
)
mesh = assembly.to_mesh(tolerance=1e-3)
```

Expected behavior:

- Reusing the same `Part` instance creates separate placed instances.
- Nested assemblies flatten recursively.
- Assembly cycles are rejected with `ProductError`.
- Assembly flattening applies parent pose before child pose in a documented,
  tested order.
- Assemblies never imply boolean union.

## Viewing

```python
from cady import Camera, DirectionalLight, Scene

scene = (
    Scene.from_assembly(assembly)
    .with_camera(Camera.look_at(position=(160, -180, 120), target=(60, 40, 0)))
    .with_light(DirectionalLight(direction=(-1, -1, -2), intensity=2.0))
)
```

Expected behavior:

- `Scene` stores targets and view state only.
- `Camera` and `Light` import no visualisation backend.
- Direct calls such as `view(assembly, tolerance=...)` may create a default
  `Scene` internally, but the backend adapter consumes scene-compatible data.

## File Export

```python
from cady.files import dxf, stl, step

dxf.write(drawing, "front.dxf", tolerance=1e-3)
stl.write(part, "plate.stl", ascii=False, tolerance=1e-3)
step.write(assembly, "assembly.step")
```

Expected behavior:

- DXF only accepts `Drawing2D`.
- STL accepts `Mesh3D`, `Body3D`, `Part`, `Assembly`, and `Document` targets
  that contain meshable 3D geometry.
- STEP accepts supported `Body3D`, `Part`, `Assembly`, and `Document` targets.
- Document export chooses appropriate contents by format:
  - DXF requires exactly one drawing or an explicit drawing argument;
  - STL merges all meshable 3D contents;
  - STEP writes all supported parts/assemblies, flattening assemblies first.

## Removed API

The following should fail to import after the replacement:

```python
from cady import Model, DxfDrawing, StlMesh, Shape2D, Shape3D
from cady import Rectangle, Prism, Sphere, Extrusion, Revolution
```

The following facade functions should not exist:

```python
cady.files.dxf.write_model
cady.files.stl.write_model
cady.files.step.write_model
```
