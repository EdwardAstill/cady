# API Guide

Import the common value objects from `cady`. Import subpackages when you need a
specific facade or lower-level numeric type.

## Common imports

```python
from cady import (
    Assembly,
    Body3D,
    Camera,
    Document,
    Drawing2D,
    Part,
    Profile2D,
    Scene,
    circle2d,
    line2d,
    profile_rectangle,
)
from cady.files import dxf, step, stl
from cady.numeric import Transform3
```

## 2D geometry

Classes:

- `Line2D(start, end)`
- `Arc2D(centre, radius, start_rad, end_rad)`
- `Polyline2D(vertices)`
- `ClosedPolyline2D(vertices)`
- `Circle2D(centre, radius)`
- `Ellipse2D(centre, radius_x, radius_y, rotation_rad=0.0)`
- `Spline2D(control_points, closed=False)`
- `Profile2D(outer, holes=())`

Factories:

- `line2d(start, end)`
- `arc2d(centre, radius, start_rad, end_rad)`
- `circle2d(centre, radius)`
- `polyline2d(vertices, closed=False)`
- `profile_rectangle(width, height, origin=(0.0, 0.0))`
- `profile_circle(radius, centre=(0.0, 0.0))`

Useful methods:

- `bounds()`
- `points()`
- `to_array(tolerance=...)`

Closed curves and profiles evaluate to `ArrayPolygon2`; open curves evaluate to
`ArrayPolyline2`.

## 3D geometry

Classes:

- `Frame3D(origin, x_axis, normal)`
- `Face3D(profile, frame)`
- `Body3D(name=None, features=(), metadata={})`
- `Mesh3D(vertices, faces, edges=())`

Factories:

- `box(width, depth, height, frame=None)`
- `cylinder(radius, height, frame=None)`
- `sphere(radius, centre=(0.0, 0.0, 0.0))`

Useful constructors and methods:

- `Frame3D.world_xy()`
- `Frame3D.from_normal(origin, normal, x_axis=None)`
- `Face3D.from_profile(profile, frame=None, origin=None, normal=None, x_axis=None)`
- `Face3D.from_points(points)`
- `Face3D.convex_hull(points)`
- `Body3D.from_profile(profile, frame=None)`
- `Body3D.extrude(distance, profile=None, frame=None)`
- `Body3D.transformed(transform)`
- `Body3D.to_mesh(tolerance=...)`
- `Mesh3D.from_dxf(path)`
- `Mesh3D.to_array(tolerance=...)`
- `Mesh3D.transformed(transform)`
- `Mesh3D.bounds()`
- `Mesh3D.view(...)`, `Body3D.view(...)`, `Face3D.view(...)`

## Drawings

```python
drawing = (
    Drawing2D("front")
    .add_layer("PLATE", color=7)
    .add(profile.outer, layer="PLATE")
    .add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="PLATE")
)
```

Key drawing methods:

- `add_layer(layer_or_name, color=7, linetype="CONTINUOUS")`
- `add(geometry, layer="0")`
- `add_entity(entity)`
- `add_text(text, at=..., height=..., layer="0", rotation=0.0)`
- `hatch(boundary, layer="0", pattern="ANSI31", angle=45.0, scale=1.0)`
- `add_block(block)`
- `insert(name, at=..., layer="0", scale=1.0, rotation=0.0)`
- `with_dim_style(style)`
- `linear_dimension(...)`, `aligned_dimension(...)`, `radius_dimension(...)`,
  `diameter_dimension(...)`, `angular_dimension(...)`
- `bounds()`
- `to_arrays(tolerance=...)`

Supported linetypes are `CONTINUOUS`, `HIDDEN`, and `CENTER`.

## Product structure

```python
from cady import Assembly, Material, Part

part = (
    Part("plate")
    .with_body(body)
    .with_material(Material("steel", density=7850.0, color=(0.6, 0.6, 0.62)))
    .with_metadata(item="P-001")
)

assembly = Assembly("assy").add(part, name="plate", pose=(0.0, 0.0, 0.0))
```

Key methods:

- `Part.with_body(body)`, `Part.with_bodies(*bodies)`
- `Part.with_material(material)`
- `Part.with_metadata(**metadata)`
- `Part.to_mesh(tolerance=...)`
- `Part.view(...)`
- `Assembly.add(part_or_assembly, name=None, pose=None)`
- `Assembly.flatten()`
- `Assembly.to_mesh(tolerance=...)`
- `Assembly.view(...)`

## Documents

```python
document = (
    Document("job", units="m")
    .add_drawing(drawing, name="front")
    .add_part(part)
    .add_assembly(assembly)
    .add_scene(scene, name="review")
)

document.names("part")
document.get("drawing", "front")
```

Kinds are `"drawing"`, `"part"`, `"assembly"`, and `"scene"`.

## Scenes

```python
from cady import Camera, DirectionalLight, DisplayStyle, Scene

scene = (
    Scene.from_target(part, name="review")
    .with_camera(Camera.look_at(position=(2, -2, 1), target=(0, 0, 0)), name="iso")
    .with_light(DirectionalLight(direction=(-1, -1, -2)))
)
```

Scene objects carry a target, optional pose, optional style, and metadata.
Scenes are backend-independent and do not import viewer libraries.

## File facades

```python
dxf.write(drawing, "front.dxf", tolerance=1e-3)
rendered = dxf.render(drawing, tolerance=1e-3)
imported = dxf.read_drawing("front.dxf")
mesh = dxf.read_mesh("mesh.dxf")
result = dxf.read("mixed.dxf")

stl.write(part, "plate.stl", tolerance=1e-3)
stl.write(assembly, "assembly-ascii.stl", ascii=True, tolerance=1e-3)

step.write(part, "plate.step", tolerance=1e-3)
text = step.render(assembly, tolerance=1e-3)
faces = step.read_faces("member.step")
members = step.read_members("member.step")
```

The old `write_model(...)` facade functions are intentionally absent.

## Errors

```python
from cady import CadError, DrawingError, GeometryError, ProductError, ReadError, ViewError, WriteError
```

Use the specific error tier when raising from package code and catch `CadError`
when user code wants one shared base exception.
