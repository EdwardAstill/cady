# Object Model

cady uses immutable value objects. Methods that sound mutating, such as
`.add(...)`, `.with_body(...)`, and `.with_metadata(...)`, return new objects.

## Layers of objects

```text
Document
  drawings -> named Drawing2D values
  parts -> named Part values
  assemblies -> named Assembly values
  scenes -> named Scene values

Drawing2D
  layers -> Layer values
  entities -> DrawingEntity, Text2D, Hatch2D, Insert2D, dimensions
  blocks -> BlockDefinition values
  dim_styles -> DimStyle values

Part
  bodies -> meshable Body3D, Mesh3D, ArrayMesh3, or compatible objects
  material
  metadata

Assembly
  part instances
  assembly instances

Scene
  scene objects
  cameras
  lights
  display styles
```

`Document` is a registry. It does not own a hidden modelling kernel and it is
not required for normal drawing, part, assembly, or scene work.

## 2D geometry

2D authoring objects live in `cady.geometry2d` and are re-exported from
`cady`:

- `Line2D`, `Arc2D`, `Polyline2D`, and `Spline2D` are open curves.
- `Circle2D`, `Ellipse2D`, and `ClosedPolyline2D` are closed curves.
- `Profile2D` represents a filled region with one outer closed curve and zero
  or more closed holes.

Factories cover the common cases:

```python
from cady import Profile2D, circle2d, line2d, polyline2d, profile_rectangle

outline = profile_rectangle(4.0, 2.0, origin=(1.0, 1.0))
hole = circle2d((3.0, 2.0), 0.4)
profile = Profile2D(outline.outer, holes=(hole,))
edge = line2d((0.0, 0.0), (1.0, 0.0))
```

`Profile2D.to_array(tolerance=...)` returns an `ArrayPolygon2`. Open curves
return `ArrayPolyline2`.

## 3D geometry

3D authoring objects live in `cady.geometry3d`:

- `Frame3D` places local 2D coordinates in 3D space.
- `Face3D` places a profile or point loop on a frame.
- `Body3D` stores meshable primitive/profile/extrude features.
- `Mesh3D` stores evaluated vertices with triangle face indices and optional
  explicit edge indices for wire geometry.

Convenience primitives return `Body3D`:

```python
from cady import Body3D, Part, box, cylinder, sphere

plate_body = Body3D.from_profile(profile).extrude(0.04)
box_body = box(1.0, 0.6, 0.04)
pin_body = cylinder(0.05, 0.08)
ball = sphere(0.5, centre=(0.0, 0.0, 0.5))

part = Part("plate").with_body(plate_body)
mesh = part.to_mesh(tolerance=1e-3)
```

`Body3D.to_mesh(tolerance=...)` returns `Mesh3D`. `Part.to_mesh(...)` and
`Assembly.to_mesh(...)` return `ArrayMesh3`.

## Drawings

`Drawing2D` is the 2D drafting object used by the DXF facade:

```python
from cady import Drawing2D

drawing = (
    Drawing2D("front", units="m")
    .add_layer("PLATE", color=7)
    .add_layer("CENTER", color=3, linetype="CENTER")
    .add(profile.outer, layer="PLATE")
    .add(hole, layer="PLATE")
    .add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="PLATE")
    .linear_dimension((0.0, 0.0), (1.0, 0.0), offset=-0.08)
)
```

The drawing model includes hatches, blocks, inserts, and dimensions. The
current DXF writer emits the basic geometry/text subset described in
[File formats](files/index.md).

## Parts and assemblies

`Part` names one manufacturable item. `Assembly` places parts and
subassemblies without merging their geometry:

```python
from cady import Assembly, Part, box

plate = Part("plate").with_body(plate_body)
pin = Part("pin").with_body(box(0.1, 0.1, 0.08))

assembly = (
    Assembly("production_plate")
    .add(plate, name="plate")
    .add(pin, name="pin", pose=(0.45, 0.25, 0.04))
)

flattened = assembly.flatten()
mesh = assembly.to_mesh(tolerance=1e-3)
```

An instance `pose` may be `None`, a `Transform3`, a `Pose3`-like object with
`to_transform3()`, or a 3D translation tuple.

## Scenes

`Scene` is for viewing and presentation state:

```python
from cady import Camera, DirectionalLight, DisplayStyle, Scene

scene = (
    Scene("review")
    .add(part, style=DisplayStyle(color=(0.74, 0.78, 0.82)))
    .with_camera(
        Camera.perspective(position=(1.7, -1.6, 0.9), target=(0.5, 0.3, 0.05)),
        name="iso",
    )
    .with_light(DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.6))
)
```

Scenes do not change the CAD truth. They reference targets and add view-specific
cameras, lights, poses, styles, and metadata.

## Numeric objects

The numeric package stores evaluated arrays:

- `ArrayPolyline2`
- `ArrayPolygon2`
- `ArrayPolyline3`
- `ArrayMesh3`
- `Transform2`
- `Transform3`
- `Pose3`

Numeric modules do not import authoring packages. Authoring objects adapt their
own fields into primitive values before calling numeric or ops functions.
