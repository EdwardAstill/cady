# New API Sketch

## Overview

This is a design sketch for a simpler object model. The main split is:

- 2D curves describe boundaries.
- 2D profiles describe filled regions.
- 3D faces place profiles in space.
- 3D bodies are made by features such as extrude, revolve, and boolean union.
- Meshes are evaluated triangle data, not the main authoring format.

## Object Hierarchy

```text
Model
  objects -> Object2D | Object3D
  layers/groups -> named collections of objects

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
Compound3D = grouped objects, separate geometry
BooleanUnionFeature = merged solid body
```

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

