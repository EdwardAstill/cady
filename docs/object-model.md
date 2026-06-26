# Object model

cady's objects are immutable frozen dataclasses. Every method that "adds" or
"changes" returns a new instance. Every conversion to arrays or meshes takes an
explicit `tolerance` keyword.

## Vectors: Vec2 and Vec3

`Vec2(x, y)` and `Vec3(x, y, z)` are the fundamental point/vector types. They
are frozen and support arithmetic:

```python
from cady import Vec2, Vec3

p = Vec2(1.0, 2.0)
q = Vec2(3.0, 4.0)
mid = (p + q) * 0.5          # Vec2(2.0, 3.0)
length = (q - p).length()    # Euclidean distance

v = Vec3(1.0, 0.0, 0.0)
n = v.normalised()           # unit vector
dot = v.dot(Vec3(0.0, 1.0, 0.0))  # 0.0
cross = v.cross(Vec3(0.0, 1.0, 0.0))  # Vec3(0.0, 0.0, 1.0)
```

Most functions accept plain tuples as point arguments — they are promoted
internally:

```python
from cady import line2d
l = line2d((0.0, 0.0), (1.0, 0.5))  # tuples work everywhere
```

## 2D geometry

### Open curves

`Curve2D` is a protocol covering four open curve types:

**`Line2D(start, end)`** — straight line segment.

```python
from cady import Line2D, line2d

l = Line2D(Vec2(0.0, 0.0), Vec2(1.0, 0.0))
l = line2d((0.0, 0.0), (1.0, 0.0))  # constructor helper
l.bounds()      # (Vec2(0.0, 0.0), Vec2(1.0, 0.0))
l.points()      # (Vec2(0.0, 0.0), Vec2(1.0, 0.0))
l.to_array(tolerance=1e-3)  # ArrayPolyline2
```

**`Arc2D(centre, radius, start_rad, end_rad)`** — circular arc. Angles in
radians, CCW from positive x-axis.

```python
from cady import Arc2D, arc2d
from math import pi

a = arc2d((0.0, 0.0), 1.0, 0.0, pi)  # semicircle from (1,0) to (-1,0)
a.centre       # Vec2(0.0, 0.0)
a.radius       # 1.0
a.start_rad    # 0.0
a.end_rad      # 3.14159...
a.to_array(tolerance=1e-3)  # sampled polyline
```

**`Polyline2D(vertices)`** — open chain of line segments.

```python
from cady import Polyline2D, polyline2d

p = polyline2d(((0.0, 0.0), (0.5, 0.3), (1.0, 0.0)))
p.vertices     # tuple of 3 Vec2
p.to_array(tolerance=1e-3)  # ArrayPolyline2(closed=False)
```

**`Spline2D(control_points, closed=False)`** — cubic Bezier spline. Control
point count must be 3n + 1 (e.g. 4, 7, 10...).

```python
from cady import Spline2D

s = Spline2D((
    (0.0, 0.0), (0.3, 0.5), (0.7, 0.5), (1.0, 0.0),
))
s.closed       # False
s.to_array(tolerance=1e-3)  # sampled polyline via ArrayBezierSpline2
```

### Closed curves

`ClosedCurve2D` is a protocol covering three closed boundary types:

**`Circle2D(centre, radius)`** — full circle.

```python
from cady import Circle2D, circle2d

c = circle2d((0.5, 0.5), 1.0)
c.centre       # Vec2(0.5, 0.5)
c.radius       # 1.0
c.to_array(tolerance=1e-3)  # ArrayPolygon2
```

**`Ellipse2D(centre, radius_x, radius_y, rotation_rad=0.0)`** — ellipse with
optional rotation.

```python
from cady import Ellipse2D

e = Ellipse2D((0.0, 0.0), 2.0, 1.0, rotation_rad=0.25)
e.radius_x     # 2.0
e.radius_y     # 1.0
e.to_array(tolerance=1e-3)  # sampled polygon
```

**`ClosedPolyline2D(vertices)`** — closed polygon boundary. At least three
vertices. Duplicate start/end points are automatically deduplicated.

```python
from cady import ClosedPolyline2D, polyline2d

p = polyline2d(((0.0, 0.0), (1.0, 0.0), (1.0, 0.6), (0.0, 0.6)), closed=True)
# returns ClosedPolyline2D
p.vertices     # tuple of 4 Vec2 (deduplicated)
p.to_array(tolerance=1e-3)  # ArrayPolygon2
p.to_mesh(tolerance=1e-3)   # Mesh2D
```

### Mesh2D

`Mesh2D(vertices, faces, edges=())` is a 2D triangle mesh. It is useful when a
closed 2D boundary needs explicit triangle faces instead of an `ArrayPolygon2`.

```python
from cady import ClosedPolyline2D, Mesh2D

outline = ClosedPolyline2D(((0, 0), (1, 0), (1, 1), (0, 1)))
mesh = outline.to_mesh(tolerance=1e-3)  # Mesh2D
vertices, faces, edges = mesh.to_array(tolerance=1e-3)
```

### Profiles

`Profile2D(outer, holes=())` is a filled region. The outer boundary is a
`ClosedCurve2D`; holes are a tuple of `ClosedCurve2D` values.

```python
from cady import Profile2D, circle2d, profile_rectangle, profile_circle

# From an explicit boundary
outline = profile_rectangle(1.0, 0.6)
hole = circle2d((0.5, 0.3), 0.12)
profile = Profile2D(outline.outer, holes=(hole,))

# Convenience class methods
rect = Profile2D.rectangle(width=1.0, height=0.6, origin=(0.0, 0.0))
disc = Profile2D.circle(radius=0.5, centre=(0.0, 0.0))

# With multiple holes
profile = Profile2D(
    profile_rectangle(2.0, 1.0).outer,
    holes=(
        circle2d((0.5, 0.5), 0.2),
        circle2d((1.5, 0.5), 0.15),
    ),
)
```

Profiles hold geometry that can be placed in 3D via `Face3D` or extruded via
`Body3D.from_profile(profile).extrude(distance)`.

## 3D geometry

### Frame3D

`Frame3D(origin, x_axis, normal)` places local 2D coordinates in 3D space.
Points in the frame are expressed as `origin + u * x_axis + v * y_axis` where
`y_axis = normal × x_axis`. The x_axis is orthonormalised against normal on
construction.

```python
from cady import Frame3D, Vec3

# Default: XY plane at origin
frame = Frame3D.world_xy()

# From a normal vector
frame = Frame3D.from_normal(
    origin=Vec3(1.0, 0.0, 0.0),
    normal=Vec3(0.0, 1.0, 0.0),  # YZ plane
)
frame = Frame3D.from_normal(
    origin=(0.0, 0.0, 5.0),
    normal=(0.0, 0.0, 1.0),
    x_axis=(1.0, 0.0, 0.0),  # explicit x-axis hint
)

# Map 2D coordinates to 3D
p3 = frame.point(u=0.5, v=0.3)  # Vec3 in world space
```

### Face3D

`Face3D(profile, frame)` places a 2D profile into a 3D frame. The profile is
any object with a `to_array(tolerance=...)` method (typically a `Profile2D`,
`ClosedCurve2D`, or `ClosedPolyline2D`).

```python
from cady import Face3D, Profile2D

face = Face3D.from_profile(
    Profile2D.rectangle(width=1.0, height=0.6),
    origin=(0.0, 0.0, 0.0),
    normal=(0.0, 0.0, 1.0),
)

# From arbitrary 3D points
pts = (Vec3(0,0,0), Vec3(1,0,0), Vec3(1,1,0), Vec3(0,1,0), Vec3(0.5,0.5,0.2))
face3d = Face3D.from_points(pts)

# Convex hull of 3D points
hull = Face3D.convex_hull(pts)

mesh = face.to_mesh(tolerance=1e-3)  # Mesh3D
```

### Body3D

`Body3D` is editable solid geometry with a feature history. Features are
evaluated lazily; call `to_mesh(tolerance=...)` to compute the triangle mesh.

**Creating bodies:**

```python
from cady import Body3D

# From a 2D profile with extrusion
body = Body3D.from_profile(profile).extrude(0.04)

# Primitive constructors
body = Body3D.box(width=1.0, depth=0.6, height=0.04)
body = Body3D.cylinder(radius=0.5, height=2.0)
body = Body3D.sphere(radius=0.5, centre=(0.0, 0.0, 0.5))

# Or use top-level constructor helpers
from cady import box, cylinder, sphere
body = box(width=1.0, depth=0.6, height=0.04)
```

**Feature history:**

```python
body = Body3D(name="bracket")                       # empty body
body = body.with_feature(ProfileFeature(profile, frame))  # add profile
body = body.extrude(0.04)                           # extrude last profile
body = body.transformed(Transform3.translation(1, 0, 0))  # transform
```

Feature types: `ProfileFeature`, `ExtrudeFeature`, `RevolveFeature`,
`PrimitiveFeature`, `BooleanFeature`, `FilletFeature`, `ChamferFeature`.

Currently evaluated features: profile extrusion, box/cylinder/sphere primitives.
Revolve, boolean, fillet, and chamfer record types exist but evaluation is not
yet implemented (raises `NotImplementedError`).

**Evaluation:**

```python
mesh = body.to_mesh(tolerance=1e-3)  # Mesh3D

# Direct viewing (opens a vispy window)
body.view(tolerance=1e-3)
```

### Mesh3D

`Mesh3D(vertices, faces, edges=())` is a semantic triangle mesh — vertices are
`Vec3`, faces are `(i, j, k)` index triples, edges are optional `(i, j)` index
pairs.

```python
from cady import Mesh3D

# Construction
mesh = Mesh3D(
    vertices=(Vec3(0,0,0), Vec3(1,0,0), Vec3(0,1,0)),
    faces=((0, 1, 2),),
)

# Properties
mesh.vertices          # tuple[Vec3, ...]
mesh.faces             # tuple[tuple[int, int, int], ...]
mesh.triangles         # tuple[tuple[Vec3, Vec3, Vec3], ...]
mesh.boundary          # ArrayPolyline3 of boundary edges
mesh.boundary_loops    # tuple of ArrayPolyline3, one per hole

# Bounds
mesh.bounds()          # (Vec3 min, Vec3 max)

# Transforms (return new Mesh3D)
mesh.transformed(Transform3.translation(1, 0, 0))
mesh.mirror(plane_origin, plane_normal)

# Conversion
vertices, faces, edges = mesh.to_array(tolerance=1e-3)

# Merge multiple meshes (with index offsets)
merged = Mesh3D.merged([mesh1, mesh2])

# Close open boundaries
capped = mesh.close_planar(plane_origin, plane_normal, tolerance=1e-3)
walls = mesh.close_to_plane(plane_origin, plane_normal, max_distance=0.1)
closed = mesh.close_boundary(tolerance=1e-3)
# mesh.close_holes(tolerance=1e-3)  # not yet implemented

# Convert to wireframe
wf = mesh.to_wireframe()  # Wireframe3D (edges only, no faces)
```

### 3D polylines

`Polyline3D(vertices)` is open wire data. `ClosedPolyline3D(vertices)` is a
planar closed boundary loop that can be triangulated to `Mesh3D`.

```python
from cady import ClosedPolyline3D

loop = ClosedPolyline3D(((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)))
mesh = loop.to_mesh(tolerance=1e-3)  # Mesh3D
```

### Wireframe3D

`Wireframe3D(vertices, edges)` is edge-only 3D geometry — vertices connected
by edges, with no faces.

```python
from cady import Wireframe3D

wf = Wireframe3D(
    vertices=(Vec3(0,0,0), Vec3(1,0,0), Vec3(1,1,0), Vec3(0,1,0)),
    edges=((0, 1), (1, 2), (2, 3), (3, 0)),
)

wf.vertices    # tuple[Vec3, ...]
wf.edges       # tuple[tuple[int, int], ...]
wf.bounds()    # (Vec3 min, Vec3 max)
wf.transformed(Transform3.translation(0, 0, 1))
wf.mirror(plane_origin, plane_normal)
wf.to_array(tolerance=1e-3)  # (vertices, empty faces, edges)
wf.to_mesh(tolerance=1e-3)   # Mesh3D

# Split crossings, remove dangling edges, and triangulate to triangle wires
triangulated = wf.triangulate(tolerance=1e-3)  # Wireframe3D

# View
wf.view(tolerance=1e-3)
```

Wireframes can be imported from DXF:

```python
from cady.files import dxf
wf = dxf.read_wireframe("hull_wires.dxf")
```

## Drawings

`Drawing2D` is a 2D drafting document with named layers, geometry entities,
text, hatches, blocks, and dimensions.

### Layers

```python
from cady import Drawing2D, Layer

drawing = Drawing2D("front")
drawing = drawing.add_layer("PLATE", color=7)           # white/black
drawing = drawing.add_layer("CENTER", color=3, linetype="CENTER")
drawing = drawing.add_layer("TEXT", color=2)            # yellow
drawing = drawing.add_layer("DIMENSIONS", color=1)      # red

# Query
layer = drawing.layer("PLATE")  # Layer or None
```

Layer colors are AutoCAD Color Index values (1–255). Supported linetypes:
`CONTINUOUS`, `HIDDEN`, `CENTER`.

### Geometry entities

```python
from cady import line2d, circle2d, profile_rectangle
profile = profile_rectangle(1.0, 0.6)
hole = circle2d((0.5, 0.3), 0.12)

drawing = (
    drawing
    .add(profile.outer, layer="PLATE")     # any curve
    .add(hole, layer="PLATE")
    .add(line2d((0.0, 0.0), (1.0, 0.0)), layer="PLATE")
)

# Explicit entity construction
from cady import DrawingEntity
entity = DrawingEntity(line2d((0.0, 0.0), (1.0, 0.0)), layer="PLATE")
drawing = drawing.add_entity(entity)
```

### Text

```python
drawing = drawing.add_text(
    "PLATE",
    at=(0.02, 0.02),
    height=0.03,
    layer="TEXT",
    rotation=0.0,         # radians, optional
)
```

### Hatches

```python
drawing = drawing.hatch(
    profile.outer,
    layer="PLATE",
    pattern="ANSI31",     # only pattern currently supported
    angle=45.0,
    scale=1.0,
)
```

### Blocks and inserts

```python
from cady import BlockDefinition, circle2d

# Define a reusable block
bolt_block = (
    BlockDefinition("bolt")
    .add(circle2d((0.0, 0.0), 0.02), layer="BOLTS")
)
drawing = drawing.add_block(bolt_block)

# Insert it at multiple positions
drawing = (
    drawing
    .insert("bolt", at=(0.2, 0.2), layer="BOLTS")
    .insert("bolt", at=(0.8, 0.2), layer="BOLTS", rotation=0.5)
    .insert("bolt", at=(0.5, 0.4), layer="BOLTS", scale=0.5)
)
```

### Dimensions

```python
drawing = (
    drawing
    .linear_dimension((0.0, 0.0), (1.0, 0.0), offset=-0.08)
    .aligned_dimension((0.0, 0.0), (1.0, 0.6), offset=0.15)
    .radius_dimension((0.5, 0.3), 0.12, angle=0.5, text="4X R0.12")
    .diameter_dimension((0.5, 0.3), 0.12, angle=1.5)
    .angular_dimension((0.5, 0.3), (1.0, 0.3), (0.8, 0.6), distance=0.3)
)
```

Text values auto-format from the measured distance when not specified.
Dimension styles:

```python
from cady import DimStyle

custom = DimStyle(
    name="Precision",
    text_height=0.15,
    arrow_size=0.15,
    decimal_places=2,
)
drawing = drawing.with_dim_style(custom)
```

### Drawing metadata

```python
drawing = (
    drawing
    .with_header("$INSUNITS", 4)     # mm
    .with_metadata("author", "cady")
)

# Bounds of all entities
min_pt, max_pt = drawing.bounds()
```

## Product structure

### Part

`Part(name)` is one named manufacturable item holding one or more meshable
bodies.

```python
from cady import Part, Material

part = (
    Part("plate")
    .with_body(body)                                   # single body
    .with_bodies(body1, body2)                         # multiple bodies
    .add_body(body3)                                   # alias for with_body
    .with_material(Material("steel", density=7850.0))  # kg/m³
    .with_metadata(item="P-001", revision="A")
)

# Multiple bodies are merged on mesh evaluation
mesh = part.to_mesh(tolerance=1e-3)  # Mesh3D
```

### Material

```python
material = Material(
    "aluminium",
    density=2700.0,
    color=(0.75, 0.78, 0.82),
)
material = material.with_metadata(source="AMS 4027")
```

### Assembly

`Assembly(name)` is a tree of placed parts and subassemblies. Cycle detection
rejects structural loops.

```python
from cady import Assembly

pin = Part("pin").with_body(Body3D.cylinder(radius=0.05, height=0.08))

assembly = (
    Assembly("fixture")
    .add(part, name="plate")                           # Part in default pose
    .add(pin, name="pin_a", pose=(0.45, 0.25, 0.04))  # Part with translation
    .add(pin, name="pin_b", pose=Pose3D.at(0.55, 0.25, 0.04))
    .with_metadata(project="FIX-001")
)

# Subassemblies
sub = Assembly("sub").add(pin, name="pin")
assembly = assembly.add(sub, name="group_a", pose=(1.0, 0.0, 0.0))

# Flatten to list of placed parts
flattened = assembly.flatten()  # tuple[FlattenedPart, ...]
for item in flattened:
    print(item.part.name, item.name, item.transform, item.path)

# Evaluate to merged mesh
mesh = assembly.to_mesh(tolerance=1e-3)  # Mesh3D
```

Pose accepts: `None` (identity), a 3-tuple `(x, y, z)` translation, a
`Transform3`, or any object with `to_transform3()`.

## Viewing

### Scene

`Scene` holds cameras, lights, display styles, and references to viewable
objects. It is backend-independent; `cady.view` also exposes lazy viewer helpers
that translate scenes for display when called.

```python
from cady import Scene, Camera, DirectionalLight, AmbientLight, DisplayStyle

# From a target
scene = Scene.from_target(assembly, name="review")

# Manual construction
scene = (
    Scene("review")
    .add(assembly, style=DisplayStyle(color=(0.74, 0.78, 0.82)))
    .add(part, name="plate_detail", style=DisplayStyle(render_mode="wireframe"))
    .with_camera(
        Camera.perspective(
            position=(1.7, -1.6, 0.9),
            target=(0.5, 0.3, 0.05),
            fov_degrees=35.0,
        ),
        name="iso",
    )
    .with_camera(
        Camera.orthographic(
            position=(0.0, 0.0, 5.0),
            target=(0.0, 0.0, 0.0),
            scale=2.0,
        ),
        name="top",
        active=False,
    )
    .with_light(DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.6))
    .with_light(AmbientLight(intensity=0.3))
)
```

### Camera

```python
# Perspective (default)
camera = Camera.perspective(
    position=(1.7, -1.6, 0.9),
    target=(0.5, 0.3, 0.0),
    up=(0.0, 0.0, 1.0),      # optional
    fov_degrees=45.0,          # optional
)

# Orthographic
camera = Camera.orthographic(
    position=(0.0, 0.0, 5.0),
    target=(0.0, 0.0, 0.0),
    scale=1.0,                 # optional
)

# Generic look-at
camera = Camera.look_at(
    position=(2.0, -2.0, 1.0),
    target=(0.0, 0.0, 0.0),
)
```

Camera parameters: `position`, `target`, `up`, `projection` (`"perspective"` or
`"orthographic"`), `fov_degrees`, `orthographic_scale`, `near`, `far`.

### Lights

```python
# Ambient (fill light)
AmbientLight(intensity=0.3, color=(1.0, 1.0, 1.0))

# Directional (sun-like)
DirectionalLight(
    direction=(-1.0, -1.0, -2.0),
    intensity=1.6,
    color=(1.0, 0.95, 0.9),
)

# Point (positional)
PointLight(
    position=(5.0, 5.0, 5.0),
    intensity=2.0,
    range=10.0,               # optional attenuation range
)
```

`Light` is also a base class you can subclass for custom light types.

### DisplayStyle

```python
style = DisplayStyle(
    color=(0.74, 0.78, 0.82),
    opacity=0.8,
    render_mode="shaded",      # "shaded", "wireframe", or "points"
    line_width=1.5,
    point_size=4.0,
    visible=True,
)
```

### Direct viewing

Most objects support a `.view()` convenience method that opens a vispy window
without creating a Scene explicitly:

```python
body.view(tolerance=1e-3, title="My Part")
part.view(camera=Camera.perspective(position=(1,1,1), target=(0,0,0)))
assembly.view(render_mode="wireframe")
mesh.view(color=(0.2, 0.6, 1.0))
wireframe.view()
```

The `.view()` method accepts: `name`, `title`, `camera`, `style`, `light`,
`color`, `render_mode`, `projection`, `center`, `tolerance`.

## Document

`Document(name, units="m")` is an optional registry of named drawings, parts,
assemblies, and scenes. It is never required — file writers and viewers accept
direct objects.

```python
from cady import Document

doc = (
    Document("plate_job", units="m")
    .add_drawing(drawing, name="front")
    .add_part(part, name="plate")
    .add_assembly(assembly, name="fixture")
    .add_scene(scene, name="review")
    .with_metadata(author="cady", revision="2")
)

# Lookup
drawing = doc.get("drawing", "front")
part = doc.get("part", "plate")
doc.names("drawing")           # ("front",)
doc.names("part")              # ("plate",)
doc.names("scene")             # ("review",)
```

Items auto-name from their `.name` attribute when not given explicitly.

## Evaluation boundary

```text
domain objects  →  .to_array(tolerance=...)  →  numeric arrays
                →  .to_mesh(tolerance=...)   →  Mesh2D / Mesh3D / arrays
                →  dxf/stl/step.write(...)   →  files
```

Every conversion that samples curves or meshes takes an explicit `tolerance`
keyword. There are no hidden defaults.

## Viewing Helpers

The view package provides direct viewing functions:

```python
from cady.view import view_target, view_scene, view_mesh, view_lines

# View any meshable or viewable target
view_target(body, tolerance=1e-3)
view_target(part, tolerance=1e-3)
view_target(assembly, tolerance=1e-3)

# View a Scene (respects cameras, lights, styles)
view_scene(scene)

# View raw array meshes
view_mesh(array_mesh3)

# View wireframe data
view_lines(vertices_array, edges_array)

# Prepare a scene for rendering
from cady.view import prepare_scene
prepared = prepare_scene(scene)  # PreparedScene

# Create a Scene from any target
from cady.view import scene_from_target
scene = scene_from_target(assembly, name="my_scene")
```

## File I/O (quick reference)

```python
from cady.files import dxf, step, stl

# DXF
dxf.write(drawing, "front.dxf", tolerance=1e-3)
drawing = dxf.read_drawing("front.dxf")
mesh = dxf.read_mesh("3d_faces.dxf")
wireframe = dxf.read_wireframe("wires.dxf")
result = dxf.read("mixed.dxf")          # DxfImportResult

# STL
stl.write(part, "plate.stl", tolerance=1e-3)
stl.write(assembly, "asm.stl", ascii=True, tolerance=1e-3)

# STEP
step.write(part, "plate.step", tolerance=1e-3)
faces = step.read_faces("member.step")
members = step.read_members("member.step")
```
