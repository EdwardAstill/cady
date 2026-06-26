# New API Status

This note records the current clean API shape in this branch. The old
`Model`/`domain`/`build` API has been removed; use direct value objects and
file facades instead.

## Primary concepts

```text
Drawing2D   2D drafting document for DXF-oriented work
Body3D      meshable 3D authoring body
Part        named manufacturable item with one or more bodies
Assembly    placed parts and subassemblies
Scene       view/presentation state
Document    optional registry of named drawings, parts, assemblies, scenes
Mesh3D      semantic triangle mesh value
ArrayMesh3  NumPy-backed evaluated triangle mesh
```

Documents are optional. A user can work directly with a drawing, part,
assembly, scene, profile, body, or mesh.

## Minimal example

```python
from cady import Body3D, Drawing2D, Part, Profile2D, circle2d, profile_rectangle
from cady.files import dxf, stl

outline = profile_rectangle(1.0, 0.6)
hole = circle2d((0.5, 0.3), 0.12)
profile = Profile2D(outline.outer, holes=(hole,))

drawing = Drawing2D("front").add(profile.outer, layer="PLATE").add(hole, layer="PLATE")
part = Part("plate").with_body(Body3D.from_profile(profile).extrude(0.04))

dxf.write(drawing, "plate.dxf", tolerance=1e-3)
stl.write(part, "plate.stl", tolerance=1e-3)
```

## 2D representation

Open curves:

- `Line2D`
- `Arc2D`
- `Polyline2D`
- `Spline2D`

Closed curves:

- `Circle2D`
- `Ellipse2D`
- `ClosedPolyline2D`

Filled regions:

- `Profile2D(outer, holes=())`

Factories:

- `line2d(...)`
- `arc2d(...)`
- `circle2d(...)`
- `polyline2d(..., closed=False)`
- `profile_rectangle(...)`
- `profile_circle(...)`

`Rectangle2D` is intentionally not a core public type. Use
`profile_rectangle(...)` for filled rectangles or `ClosedPolyline2D` for an
explicit closed boundary.

## 3D representation

`Frame3D` places local 2D coordinates in 3D:

```text
point3d = origin + u * x_axis + v * y_axis
y_axis = normal cross x_axis
```

`Body3D` stores meshable features. Implemented mesh paths are:

- primitive box;
- primitive cylinder;
- primitive sphere;
- profile extrusion.

Feature record types for revolve, boolean, fillet, and chamfer exist, but their
evaluation is not implemented yet.

Convenience primitives:

```python
from cady import box, cylinder, sphere

body = box(1.0, 0.6, 0.04)
pin = cylinder(0.05, 0.08)
ball = sphere(0.5, centre=(0.0, 0.0, 0.5))
```

## Product structure

`Part` owns meshable bodies and product metadata:

```python
from cady import Material, Part

part = (
    Part("plate")
    .with_body(body)
    .with_material(Material("steel", density=7850.0))
    .with_metadata(item="P-001")
)
```

`Assembly` places parts or subassemblies without merging their CAD meaning:

```python
from cady import Assembly

assembly = (
    Assembly("fixture")
    .add(part, name="plate")
    .add(pin_part, name="pin", pose=(0.45, 0.25, 0.04))
)

mesh = assembly.to_mesh(tolerance=1e-3)
```

Assembly flattening composes instance transforms and returns `FlattenedPart`
records. Mesh export flattens assemblies into evaluated mesh data.

## Drawings

`Drawing2D` is the canonical 2D drafting object:

```python
drawing = (
    Drawing2D("front")
    .add_layer("PLATE", color=7)
    .add_layer("CENTER", color=3, linetype="CENTER")
    .add(profile.outer, layer="PLATE")
    .add(hole, layer="PLATE")
    .add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="PLATE")
    .linear_dimension((0.0, 0.0), (1.0, 0.0), offset=-0.08)
)
```

The value model supports hatches, blocks, inserts, and dimensions. The current
DXF writer emits basic geometry/text entities and layer records; richer drawing
entities are represented in memory but not fully emitted yet.

## Scenes

`Scene` stores view state independently from CAD/product data:

```python
from cady import Camera, DirectionalLight, DisplayStyle, Scene

scene = (
    Scene("review")
    .add(part, style=DisplayStyle(color=(0.74, 0.78, 0.82)))
    .with_camera(Camera.perspective(position=(1.7, -1.6, 0.9), target=(0.5, 0.3, 0.05)))
    .with_light(DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.6))
)
```

Scenes can reference drawings, bodies, parts, assemblies, meshes, or imported
wire data. They do not render directly and they do not alter export output.

## Documents

`Document` is a named registry:

```python
from cady import Document

document = (
    Document("job", units="m")
    .add_drawing(drawing, name="front")
    .add_part(part)
    .add_assembly(assembly)
    .add_scene(scene, name="review")
)
```

Use `document.names(kind)` and `document.get(kind, name)` for lookup. Kinds are
`"drawing"`, `"part"`, `"assembly"`, and `"scene"`.

## File facade status

```python
from cady.files import dxf, step, stl

dxf.write(drawing, "front.dxf", tolerance=1e-3)
stl.write(part, "plate.stl", tolerance=1e-3)
step.write(assembly, "assembly.step", tolerance=1e-3)
```

Current behavior:

- DXF writes basic 2D entities/text and reads basic 2D, `3DFACE`, and 3D
  polyline wire data.
- STL writes binary or ASCII triangle meshes from meshable targets.
- STEP writes a mesh-oriented ISO-10303-21 file and reads elementary
  face/member data for analysis.

Removed compatibility names include `Model`, `Shape2D`, `Shape3D`,
`Rectangle`, `Prism`, `Extrusion`, `Revolution`, `DxfDrawing`, `StlMesh`,
`cady.domain`, `cady.build`, and `write_model(...)`.

## Implementation priorities

1. Keep public docs and examples centered on direct objects, not a mandatory
   top-level registry.
2. Keep conversion boundaries explicit with `tolerance`.
3. Expand DXF output only after adding focused tests for each entity type.
4. Treat true STEP B-rep/product-structure export as a separate feature from
   the current mesh writer.
5. Keep optional viewer code as leaf code over `cady.view`, authoring objects,
   and numeric meshes.
