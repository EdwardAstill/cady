# API reference

## Top-level exports

### 2D geometry

| Name | Description |
|------|-------------|
| `Line2D` | Line segment between two points. |
| `Arc2D` | Circular arc (centre, radius, start/end angle). |
| `Spline2D` | Bezier spline curve. |
| `Polyline2D` | Open or closed polyline. |
| `Circle2D` | Full circle. |
| `Ellipse2D` | Ellipse. |
| `Region2D` | Filled region (outer boundary + holes). |
| `Mesh2D` | 2D triangle mesh. |
| `Curve2D` | Protocol for open curves. |
| `ClosedCurve2D` | Protocol for closed boundaries. |

### 3D geometry

| Name | Description |
|------|-------------|
| `Plane3D` | Coordinate plane in 3D space. |
| `Surface3D` | Parametric surface defined by `x(u,v)`, `y(u,v)`, and `z(u,v)`. |
| `Region3D` | Bounded 2D region in a surface parameter domain. |
| `Body3D` | Editable solid with feature history. |
| `Polyline3D` | Open 3D polyline. |
| `ClosedPolyline3D` | Closed planar 3D polyline loop. |
| `Mesh3D` | Evaluated triangle mesh. |
| `Wireframe3D` | Edge-only wireframe (vertices + edges). |

### Product

| Name | Description |
|------|-------------|
| `Part` | Named manufacturable item with bodies. |
| `PartInstance` | Placed part reference. |
| `Assembly` | Tree of placed parts and subassemblies. |
| `AssemblyInstance` | Placed subassembly reference. |
| `Material` | Material name and density. |

### Drawing

| Name | Description |
|------|-------------|
| `Drawing2D` | 2D drafting document. |
| `DrawingEntity` | Curve/region with layer assignment. |
| `Layer` | Named layer with color and linetype. |
| `Text2D` | Text entity. |
| `Hatch2D` | Hatch fill entity. |
| `Insert2D` | Block insertion entity. |
| `BlockDefinition` | Reusable block definition. |
| `DimStyle` | Dimension style. |
| `LinearDimension2D` | Horizontal/vertical dimension. |
| `AlignedDimension2D` | Aligned dimension. |
| `RadiusDimension2D` | Radius dimension. |
| `DiameterDimension2D` | Diameter dimension. |
| `AngularDimension2D` | Angular dimension. |

### View

| Name | Description |
|------|-------------|
| `Scene` | Named collection of view targets, cameras, lights. |
| `SceneObject` | Target reference with pose and visibility. |
| `Camera` | Perspective or orthographic camera. |
| `AmbientLight` | Ambient light. |
| `Light` | Protocol base for light sources. |
| `DirectionalLight` | Directional light. |
| `PointLight` | Point light. |
| `DisplayStyle` | Color, alpha, and edge visibility. |

### Other

| Name | Description |
|------|-------------|
| `Document` | Optional project registry. |

## Factory functions

| Function | Returns | Signature |
|----------|---------|-----------|
| `line2d(start, end)` | `Line2D` | Two points. |
| `arc2d(centre, radius, start_angle, end_angle)` | `Arc2D` | Angles in radians. |
| `circle2d(centre, radius)` | `Circle2D` | Centre point and radius. |
| `polyline2d(points, *, closed=False)` | `Polyline2D` | Sequence of points. |
| `region_rectangle(width, height, *, origin=(0,0))` | `Region2D` | Width and height. |
| `region_circle(radius, *, centre=(0,0))` | `Region2D` | Radius. |
| `box(*, width, depth, height, plane=None)` | `Body3D` | Dimensions in 3D. |
| `cylinder(*, radius, height, plane=None)` | `Body3D` | Radius and height. |
| `sphere(*, radius, centre=(0,0,0))` | `Body3D` | Radius. |

## Errors

| Exception | Use |
|-----------|-----|
| `CadError` | Base package error. |
| `GeometryError` | Invalid curve, region, or body construction. |
| `DrawingError` | Invalid drawing composition or layers. |
| `ProductError` | Invalid part/assembly structure or cycles. |
| `ViewError` | Invalid camera, light, or scene reference. |
| `ReadError` | File import failure. |
| `WriteError` | File export failure. |

## File I/O

```python
from cady.files import dxf, stl, step
```

| Function | Accepts | Action |
|----------|---------|--------|
| `dxf.read(path)` | file path | Returns `DxfImportResult`. |
| `dxf.read_drawing(path)` | file path | Returns `Drawing2D`. |
| `dxf.read_curves(path)` | file path | Returns imported 3D polyline curves with DXF metadata. |
| `dxf.read_mesh(path)` | file path | Returns `Mesh3D` from actual DXF mesh entities such as `3DFACE`. |
| `dxf.read_wireframe(path)` | file path | Returns `Wireframe3D` merged from imported 3D polyline wires. |
| `dxf.write(drawing, path, *, tolerance)` | `Drawing2D` | Writes DXF R2018. |
| `dxf.render(drawing, *, tolerance)` | `Drawing2D` | Returns DXF string. |
| `stl.write(target, path, *, ascii, tolerance)` | `Mesh3D\|Body3D\|Part\|Assembly\|Document` | Writes binary or ASCII STL. |
| `step.write(target, path, *, tolerance)` | `Body3D\|Part\|Assembly\|Document` | Writes STEP. |
| `step.render(target, *, tolerance)` | `Body3D\|Part\|Assembly\|Document` | Returns STEP string. |
| `step.read_faces(path)` | file path | Returns list of parsed faces. |
| `step.read_members(path)` | file path | Returns list of extruded members. |
