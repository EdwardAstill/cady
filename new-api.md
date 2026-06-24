# New API Sketch

## Overview

This is a design sketch for a simpler object model. The main split is:

- 2D curves describe boundaries.
- 2D profiles describe filled regions.
- 3D faces place profiles in space.
- 3D bodies are made by features such as extrude, revolve, and boolean union.
- Parts are named manufacturable objects made from one or more bodies.
- Assemblies place parts and subassemblies without automatically merging them.
- Scenes are for viewing and presentation: cameras, lights, visibility, and
  display overrides.
- Documents are optional top-level registries for files and named objects, not
  the object users must start with.
- Meshes are evaluated triangle data, not the main authoring format.

## Object Hierarchy

```text
Document
  units, metadata
  drawings -> Drawing2D[]
  parts -> Part[]
  assemblies -> Assembly[]
  scenes -> Scene[]

Part
  bodies -> Body3D[]
  material/display metadata

Assembly
  instances -> PartInstance | AssemblyInstance

PartInstance
  part -> Part
  pose -> Pose3D or Transform3D

AssemblyInstance
  assembly -> Assembly
  pose -> Pose3D or Transform3D

Scene
  objects -> SceneObject[]
  cameras -> Camera[]
  active_camera -> Camera
  lights -> Light[]
  display defaults

Object2D
  Curve2D
    Line2D
    Arc2D
    Spline2D
    Polyline2D
  ClosedCurve2D
    Circle2D
    Ellipse2D
    closed Polyline2D
  Profile2D
    outer -> ClosedCurve2D
    holes -> ClosedCurve2D[]

Object3D
  Curve3D
    Line3D
    Arc3D
    Spline3D
    Polyline3D
  Face3D
  Shell3D
  Body3D
  Compound3D
  Mesh3D
```

## Containers, Assemblies, And Viewing

The new API should not require a `Model` object as the main user-facing entry
point. A user should be able to work directly with a profile, body, part,
assembly, or scene:

```python
profile = Profile2D.rectangle(width=10, height=5)
body = profile.extrude(distance=20)
part = Part("plate", bodies=[body])
```

If cady still needs one object that stores named drawings, parts, assemblies,
scenes, units, and metadata, call it `Document` rather than `Model`.
`Document` is a project/file registry. It should not be the only way to author
geometry.

### Body Versus Part

`Body3D` is geometric and editable. It owns feature history and evaluates to a
solid boundary or mesh.

`Part` is product structure. It gives one manufacturable item a name, metadata,
default display style, material, and one or more bodies:

```text
Part
  name
  bodies -> Body3D[]
  material
  display_style
  metadata
```

Allowing multiple bodies in one part is useful for multibody CAD and imported
files, but the rule should be explicit: use multiple bodies in a part only when
they are still one item. Use an assembly when the objects are separate items.

### Assembly

`Assembly` is a tree of placed instances. It does not merge solids:

```text
Assembly
  name
  instances -> Instance[]

Instance
  name
  target -> Part | Assembly
  pose -> Pose3D or Transform3D
  metadata
```

This makes repeated parts cheap and gives cady a clean path to BOM-style
metadata later. If the user wants one merged solid, they should call a boolean
operation and produce a `Body3D`:

```python
merged = body_a.union(body_b)
```

Assembly export can start by flattening instances into evaluated solids or
meshes. Preserving STEP product structure can come later.

### Scene

`Scene` is for viewing, screenshots, and presentation. It can include bodies,
parts, assemblies, meshes, and drawings, but it should not own the CAD truth.
It owns view-specific state:

```text
Scene
  name
  objects -> SceneObject[]
  cameras -> Camera[]
  active_camera -> Camera
  lights -> Light[]
  background/display defaults

SceneObject
  target -> Body3D | Part | Assembly | Mesh3D | Drawing2D
  pose -> optional Pose3D or Transform3D
  visible -> bool
  display_style -> optional override
```

This lets the same assembly be shown normally, exploded, sectioned, hidden, or
colored for review without changing the assembly itself:

```python
scene = Scene.from_assembly(assembly)
scene = scene.with_camera(Camera.look_at(
    position=(80, -100, 60),
    target=(0, 0, 0),
    fov_degrees=35,
))
scene = scene.with_light(Light.directional(direction=(-1, -1, -2), intensity=2))
```

`Camera` should support:

- projection: `perspective` or `orthographic`;
- position;
- orientation, preferably through `look_at(position, target, up=...)` plus a
  lower-level frame/orientation constructor;
- field of view for perspective cameras;
- orthographic scale for orthographic cameras;
- near and far clipping planes.

`Light` should start small:

- ambient light: color and intensity;
- directional light: direction, color, intensity;
- point light: position, color, intensity.

Camera and light objects should be frozen, import-light value objects. They can
live in a `cady.view` module or a domain submodule, but they must not import
matplotlib, pyvista, or other visualisation backends. Backend adapters translate
them when `cady.visualisation` renders a scene.

### Compound3D

`Compound3D` overlaps with `Assembly`. Prefer `Assembly` for user-facing product
structure. Keep `Compound3D` only if cady needs a pure geometry grouping type,
for example for imported geometry or intermediate operation results where
there is no named part/assembly structure.

## 2D Representation

`Point2D` may not need to be a public object. It can be a coordinate value used
by curves.

```text
Point2D = x, y
```

Open curves:

```text
Line2D = start, end
Arc2D = center, radius, start_angle, end_angle
Spline2D = control points
Polyline2D = ordered points or ordered curve segments
```

If `Polyline2D` stores segments, each segment must connect to the next:

```text
segment[i].end == segment[i + 1].start
```

If the last endpoint equals the first start point, the polyline is closed.

Closed curves:

```text
Circle2D = center, radius
Ellipse2D = center, x_radius, y_radius, rotation
ClosedPolyline2D = closed point/segment loop
```

`Rectangle2D` does not need to be a core type. It can be a factory returning a
closed polyline or profile:

```python
profile = Profile2D.rectangle(width=10, height=5)
```

`Profile2D` represents a filled 2D region:

```text
Profile2D
  outer boundary -> ClosedCurve2D
  holes -> ClosedCurve2D[]
```

The outer boundary and holes live in the same 2D coordinate system.

## 3D Representation

3D coordinate values:

```text
Point3D = x, y, z
Vector3D = x, y, z
```

3D curves are useful for edges, paths, sweeps, wireframes, and imported data:

```text
Line3D = start, end
Arc3D = center, radius, frame, start_angle, end_angle
Spline3D = control points
Polyline3D = ordered 3D points or curve segments
```

Core 3D authoring objects:

```text
Face3D = a placed 2D profile
Shell3D = connected faces, not necessarily solid
Body3D = solid/editable body made from features
Compound3D = grouped objects, not boolean merged
Mesh3D = vertices + faces
```

Convenience primitives such as box, cylinder, cone, and sphere should be
factories that create a `Body3D` with an appropriate first feature.

## Placing A 2D Profile In 3D

A 2D profile has local coordinates `(u, v)`. To turn it into a 3D face, cady
needs a 3D coordinate frame:

```text
Frame3D
  origin -> Point3D
  x_axis -> Vector3D
  normal -> Vector3D
```

The `normal` gives the plane direction. The `x_axis` gives the rotational
orientation inside that plane. Without `x_axis`, the face can spin infinitely
around the normal, so the orientation is undefined.

The frame derives `y_axis`:

```text
normal = unit(normal)
x_axis = unit(x_axis projected onto the plane)
y_axis = normal cross x_axis
```

Then each 2D point maps into 3D as:

```text
point3d = origin + u * x_axis + v * y_axis
```

Example:

```python
profile = Profile2D.rectangle(width=10, height=5)

face = Face3D.from_profile(
    profile,
    origin=(0, 0, 20),
    normal=(0, 0, 1),
    x_axis=(1, 0, 0),
)
```

Here, the profile's local `x` direction points along world `+X`, its local `y`
direction points along world `+Y`, and the face normal points along world `+Z`.

If the user gives only `origin` and `normal`, the API can choose a deterministic
default `x_axis`, but explicit `x_axis` is better for CAD work because it avoids
surprising rotations.

## Faces From Points

There should be two different constructors:

```python
Face3D.from_points(points)
Face3D.convex_hull(points)
```

`from_points(points)` should require:

- at least 3 points;
- all points coplanar;
- points ordered around the boundary;
- no self-intersection.

This creates the face the user described.

`convex_hull(points)` should be explicit because it changes the user's input
by discarding concavity and reordering the boundary.

## Bodies And Features

`Body3D` is the main editable 3D object.

```text
Body3D
  features -> Feature[]
  evaluated boundary -> BRep/Shell3D, computed when needed
```

Features describe how the body was made:

```text
Feature
  ExtrudeFeature(profile, frame, distance)
  RevolveFeature(profile_or_face, axis, angle)
  BooleanUnionFeature(body_a, body_b)
  BooleanCutFeature(target, tool)
  BooleanIntersectFeature(body_a, body_b)
  FilletFeature(edges, radius)
  ChamferFeature(edges, distance)
```

Example:

```python
profile = Profile2D.rectangle(width=10, height=5)

body = Body3D.from_profile(profile).extrude(distance=20)

top = body.faces.by_normal("+z")
body = body.revolve(face=top, axis=Axis3D.z(), angle=90)

tool = Body3D.box(width=4, depth=4, height=20)
body = body.union(tool)
```

Generated faces need stable names or tags. An extrusion could create:

```text
start face
end face
side face for each outer boundary edge
side face for each hole boundary edge
```

This lets later features refer to a face without relying only on fragile list
indexes.

## Union Versus Grouping

Two objects next to each other are not automatically one solid.

```text
Assembly = named product structure, separate geometry
Compound3D = pure geometry group, separate geometry
BooleanUnionFeature = merged solid body
```

Prefer `Assembly` when the objects are separate parts or subassemblies. Use
`Compound3D` only for geometry-level grouping when names, instances, BOM-style
metadata, and product structure are irrelevant.

For two squares in the same 2D plane, prefer a 2D profile union first:

```python
profile = square_a.union(square_b)
body = profile.extrude(distance=10)
```

For two existing solids, use a 3D boolean:

```python
body = body_a.union(body_b)
```

2D profile booleans are much easier than 3D solid booleans, so they are a good
first target.

## Mesh Representation

`Mesh3D` should represent evaluated/faceted geometry:

```text
Mesh3D
  vertices -> Point3D[]
  faces -> index triples or index loops
```

Triangle mesh example:

```text
vertices = [
  (0, 0, 0),
  (1, 0, 0),
  (1, 1, 0),
  (0, 1, 0),
]

faces = [
  (0, 1, 2),
  (0, 2, 3),
]
```

Meshes are useful for STL export, visualisation, collision checks, and numeric
work. They should not replace semantic objects like `Circle2D`, `Profile2D`,
`Face3D`, or `Body3D` while the user is still authoring CAD geometry.

## Example API Shape

```python
profile = Profile2D.rectangle(width=120, height=80)
plate_body = profile.extrude(distance=8)
plate = Part("plate", bodies=[plate_body])

bolt = Part("m8_bolt", bodies=[Body3D.cylinder(radius=4, height=30)])

assembly = Assembly("plate_with_bolts")
assembly = assembly.add(plate, name="plate")
assembly = assembly.add(bolt, name="bolt_a", pose=Pose3D.at(20, 20, 8))
assembly = assembly.add(bolt, name="bolt_b", pose=Pose3D.at(100, 20, 8))

scene = Scene.from_assembly(assembly)
scene = scene.with_camera(Camera.look_at(
    position=(160, -180, 120),
    target=(60, 40, 0),
    fov_degrees=35,
))
scene = scene.with_light(Light.directional(direction=(-1, -1, -2)))

stl.write(plate, "plate.stl", tolerance=1e-3)
step.write(assembly, "plate_with_bolts.step")
view(scene, tolerance=1e-3)
```

This keeps the main concepts separate:

- `Body3D` is editable geometry.
- `Part` is one item.
- `Assembly` places items.
- `Scene` views items.
- `Document` collects named objects when a project/file-level object is useful.

## Implementation Plan

1. Decide public names and compatibility.
   - Prefer `Document` over `Model` for the new top-level registry.
   - Keep the old `Model` API as a compatibility wrapper or deprecated alias
     until the migration is complete.
   - Decide whether `Compound3D` remains public or becomes internal.
   - Verify with `PYTHONPATH=src .venv/bin/pytest -q tests/model tests/conventions`.

2. Add import-light value objects.
   - Add `Pose3D`/placement support if the existing transform API is not enough.
   - Add frozen `Part`, `PartInstance`, `Assembly`, and `AssemblyInstance`.
   - Add frozen `Camera`, `Light`, `Scene`, `SceneObject`, and `DisplayStyle`.
   - Do not import visualisation backends from these modules.
   - Verify with `PYTHONPATH=src .venv/bin/pytest -q tests/domain tests/model tests/conventions`.

3. Implement assembly flattening.
   - Traverse nested assemblies.
   - Apply instance poses.
   - Return evaluated bodies or meshes for writers and visualisation.
   - Verify with focused assembly tests plus `PYTHONPATH=src .venv/bin/pytest -q tests/model tests/write`.

4. Implement scene evaluation.
   - Resolve scene objects into drawable/evaluable targets.
   - Apply scene-level pose and display overrides after assembly placement.
   - Keep cameras and lights out of STL/STEP/DXF export paths unless a future
     format explicitly uses them.
   - Verify with `PYTHONPATH=src .venv/bin/pytest -q tests/visualisation tests/conventions`.

5. Update file facades.
   - Writers should accept direct geometry where sensible: `Body3D`, `Part`,
     `Assembly`, `Drawing2D`, and `Document`.
   - STL can flatten parts and assemblies into meshes.
   - STEP can initially flatten assemblies, then later preserve product
     structure.
   - DXF should remain drawing-focused.
   - Verify with `PYTHONPATH=src .venv/bin/pytest -q tests/write tests/examples`.

6. Update public docs and examples.
   - Lead with direct object usage, not `Model`.
   - Show `Part` for a single exported item.
   - Show `Assembly` for multiple placed items.
   - Show `Scene` only for viewing/presentation.
   - Verify with `PYTHONPATH=src .venv/bin/pytest -q tests/examples`.

7. Run full gates.
   - `.venv/bin/pytest -q`
   - `.venv/bin/pyright src/cady`
   - `.venv/bin/ruff check src/cady tests`

## Open Design Questions

- Should the replacement top-level registry be named `Document`,
  `CadDocument`, or something else?
- Should `Part` allow multiple bodies in the first new-API release, or should
  it start as exactly one body and expand later?
- Should `Camera`, `Light`, and `Scene` live in `cady.view`, `cady.domain.view`,
  or `cady.visualisation`? The recommended answer is `cady.view` because these
  are backend-independent value objects.
- Should STEP assembly export preserve product structure immediately, or should
  the first implementation flatten assemblies and add structured STEP later?
- Should camera orientation be stored as a frame, quaternion, matrix, or
  position/target/up? The recommended public constructor is `look_at(...)`,
  with a lower-level frame/orientation form for exact CAD views.
- How should layers, materials, and display styles interact across drawings,
  parts, assemblies, and scenes?
