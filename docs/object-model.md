# Object model

cady's objects are immutable frozen dataclasses. Every method that "adds" or
"changes" returns a new instance. Every conversion to arrays or meshes takes an
explicit `tolerance` keyword.

## 2D geometry

`Curve2D` covers open curves: `Line2D`, `Arc2D`, `Spline2D`, `Polyline2D`.

`ClosedCurve2D` covers closed boundaries: `Circle2D`, `Ellipse2D`,
`ClosedPolyline2D`.

`Profile2D` is a filled region with an outer boundary and optional holes:

```python
profile = Profile2D(outline, holes=(hole1, hole2))
profile = Profile2D.rectangle(width=120, height=80)
profile = Profile2D.circle(radius=50)
```

## 3D geometry

`Frame3D` places local 2D coordinates in 3D space.

`Face3D` is a `Profile2D` placed in a `Frame3D`.

`Body3D` is editable solid geometry with feature history:

```python
body = Body3D.from_profile(profile).extrude(8)
body = Body3D.box(width=100, depth=60, height=10)
body = Body3D.cylinder(radius=5, height=30)
body = Body3D.sphere(radius=20)
```

Call `body.to_mesh(tolerance=...)` to evaluate into `Mesh3D` for export or
viewing.

## Drawings

`Drawing2D` is a 2D drafting document with layers, geometry entities, text,
hatches, blocks, and dimensions:

```python
drawing = (
    Drawing2D("front")
    .add_layer("GEOM", color=7)
    .add(line, layer="GEOM")
    .add_text("NOTE", at=(5, 5), height=2.5, layer="TEXT")
)
```

Write to DXF with `dxf.write(drawing, path, tolerance=...)`.

## Product structure

`Part` is one named manufacturable item holding one or more `Body3D` values:

```python
part = Part("plate").with_body(body)
```

`Assembly` is a tree of placed parts and subassemblies:

```python
assembly = (
    Assembly("main")
    .add(plate, name="base")
    .add(bolt, name="bolt_a", pose=Pose3D.at(20, 20, 8))
)
```

Assemblies flatten into placed meshes for export. Cycles are rejected.

## Viewing

`Scene` holds cameras, lights, display styles, and references to objects to
view. It is backend-independent; visualisation adapters translate it into
matplotlib or pyvista state.

```python
scene = (
    Scene.from_assembly(assembly)
    .with_camera(Camera.look_at(position=(160, -180, 120), target=(60, 40, 0)))
    .with_light(DirectionalLight(direction=(-1, -1, -2)))
)
```

## Document

`Document` is an optional registry of named drawings, parts, assemblies, and
scenes. It is never required — file writers and viewers accept direct objects.

## Evaluation boundary

```text
domain objects  →  .to_array(tolerance=...)  →  numeric arrays
                →  .to_mesh(tolerance=...)   →  Mesh3D
                →  dxf/stl/step.write(...)   →  files
```
