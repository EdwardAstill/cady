# Target Files And Public Signatures

This plan intentionally replaces the existing structure. It is acceptable to
delete old files and tests that only support legacy names.

## Package Exports

### `src/cady/__init__.py`

Export only new API names and errors.

Public exports:

```python
Vec2, Vec3
Line2D, Arc2D, Spline2D, Polyline2D
Circle2D, Ellipse2D, ClosedPolyline2D
Profile2D
Frame3D, Face3D, Body3D, Mesh3D
Part, PartInstance, Assembly, AssemblyInstance
Drawing2D, Layer, BlockDefinition, DimStyle
Text2D, Hatch2D, Insert2D, LinearDimension2D, AlignedDimension2D,
RadiusDimension2D, DiameterDimension2D, AngularDimension2D
Scene, SceneObject, Camera, Light, AmbientLight, DirectionalLight,
PointLight, DisplayStyle
Document
CadError, GeometryError, DrawingError, ProductError, ViewError, ReadError,
WriteError
line2d, arc2d, circle2d, polyline2d, profile_rectangle, profile_circle,
box, cylinder, sphere
```

Do not export removed names.

### `src/cady/errors.py`

```python
class CadError(Exception): ...
class GeometryError(CadError): ...
class DrawingError(CadError): ...
class ProductError(CadError): ...
class ViewError(CadError): ...
class ReadError(CadError): ...
class WriteError(CadError): ...
```

## 2D Geometry

### `src/cady/geometry2d/curves.py`

```python
class Curve2D(Protocol): ...
class ClosedCurve2D(Curve2D, Protocol): ...

@dataclass(frozen=True, slots=True)
class Line2D:
    start: Vec2
    end: Vec2
    def bounds(self) -> tuple[Vec2, Vec2]: ...
    def points(self) -> tuple[Vec2, Vec2]: ...
    def transformed(self, transform: Transform2) -> Line2D: ...
    def to_array(self, *, tolerance: float) -> ArrayPolyline2: ...

@dataclass(frozen=True, slots=True)
class Arc2D: ...

@dataclass(frozen=True, slots=True)
class Spline2D: ...

@dataclass(frozen=True, slots=True)
class Polyline2D: ...

@dataclass(frozen=True, slots=True)
class Circle2D: ...

@dataclass(frozen=True, slots=True)
class Ellipse2D: ...

@dataclass(frozen=True, slots=True)
class ClosedPolyline2D: ...
```

`ClosedPolyline2D` stores a loop without repeating the first point.

### `src/cady/geometry2d/profile.py`

```python
@dataclass(frozen=True, slots=True)
class Profile2D:
    outer: ClosedCurve2D
    holes: tuple[ClosedCurve2D, ...] = ()
    def bounds(self) -> tuple[Vec2, Vec2]: ...
    def with_hole(self, hole: ClosedCurve2D) -> Profile2D: ...
    def transformed(self, transform: Transform2) -> Profile2D: ...
    def to_array(self, *, tolerance: float) -> ArrayPolygon2: ...
    def extrude(self, distance: float, *, frame: Frame3D | None = None) -> Body3D: ...

    @classmethod
    def rectangle(cls, *, width: float, height: float, origin: Point2Like = (0, 0)) -> Profile2D: ...
    @classmethod
    def circle(cls, *, radius: float, centre: Point2Like = (0, 0)) -> Profile2D: ...
```

### `src/cady/geometry2d/factories.py`

Factory functions:

```python
line2d(start, end) -> Line2D
arc2d(centre, radius, start_angle, end_angle) -> Arc2D
circle2d(centre, radius) -> Circle2D
polyline2d(points, *, closed: bool = False) -> Polyline2D | ClosedPolyline2D
profile_rectangle(width, height, *, origin=(0, 0)) -> Profile2D
profile_circle(radius, *, centre=(0, 0)) -> Profile2D
```

## 3D Geometry

### `src/cady/geometry3d/frame.py`

```python
@dataclass(frozen=True, slots=True)
class Frame3D:
    origin: Vec3
    x_axis: Vec3
    normal: Vec3
    @property
    def y_axis(self) -> Vec3: ...
    @classmethod
    def world_xy(cls) -> Frame3D: ...
    @classmethod
    def from_normal(cls, origin, normal, *, x_axis=None) -> Frame3D: ...
    def point(self, u: float, v: float) -> Vec3: ...
    def transformed(self, transform: Transform3) -> Frame3D: ...
```

### `src/cady/geometry3d/face.py`

```python
@dataclass(frozen=True, slots=True)
class Face3D:
    profile: Profile2D
    frame: Frame3D
    @classmethod
    def from_profile(cls, profile, *, frame=None, origin=None, normal=None, x_axis=None) -> Face3D: ...
    @classmethod
    def from_points(cls, points) -> Face3D: ...
    @classmethod
    def convex_hull(cls, points) -> Face3D: ...
    def to_mesh(self, *, tolerance: float) -> Mesh3D: ...
```

### `src/cady/geometry3d/features.py`

```python
class Feature(Protocol): ...

@dataclass(frozen=True, slots=True)
class ExtrudeFeature:
    profile: Profile2D
    frame: Frame3D
    distance: float

@dataclass(frozen=True, slots=True)
class RevolveFeature: ...

@dataclass(frozen=True, slots=True)
class PrimitiveFeature:
    kind: Literal["box", "cylinder", "sphere", "cone"]
    parameters: Mapping[str, float]
    frame: Frame3D
```

Boolean, fillet, and chamfer feature records can be defined now but may raise
`NotImplementedError` during evaluation until supported.

### `src/cady/geometry3d/body.py`

```python
@dataclass(frozen=True, slots=True)
class Body3D:
    name: str | None = None
    features: tuple[Feature, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_profile(cls, profile: Profile2D, *, frame: Frame3D | None = None) -> Body3D: ...
    @classmethod
    def box(cls, *, width: float, depth: float, height: float, frame: Frame3D | None = None) -> Body3D: ...
    @classmethod
    def cylinder(cls, *, radius: float, height: float, frame: Frame3D | None = None) -> Body3D: ...
    @classmethod
    def sphere(cls, *, radius: float, centre: Point3Like = (0, 0, 0)) -> Body3D: ...

    def extrude(self, distance: float, *, profile: Profile2D | None = None, frame: Frame3D | None = None) -> Body3D: ...
    def with_feature(self, feature: Feature) -> Body3D: ...
    def transformed(self, transform: Transform3) -> Body3D: ...
    def to_mesh(self, *, tolerance: float) -> Mesh3D: ...
```

### `src/cady/geometry3d/mesh.py`

```python
@dataclass(frozen=True, slots=True)
class Mesh3D:
    vertices: tuple[Vec3, ...]
    faces: tuple[tuple[int, int, int], ...]
    @classmethod
    def from_array(cls, mesh: ArrayMesh3) -> Mesh3D: ...
    @classmethod
    def merged(cls, meshes: Iterable[Mesh3D]) -> Mesh3D: ...
    @property
    def triangles(self) -> tuple[tuple[Vec3, Vec3, Vec3], ...]: ...
    def to_array(self, *, tolerance: float) -> ArrayMesh3: ...
    def transformed(self, transform: Transform3) -> Mesh3D: ...
    def bounds(self) -> tuple[Vec3, Vec3]: ...
```

## Drawing

### `src/cady/drawing/layers.py`

```python
@dataclass(frozen=True, slots=True)
class Layer:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"
```

### `src/cady/drawing/entities.py`

```python
@dataclass(frozen=True, slots=True)
class DrawingEntity:
    geometry: Curve2D | ClosedCurve2D | Profile2D
    layer: str = "0"

@dataclass(frozen=True, slots=True)
class Text2D: ...

@dataclass(frozen=True, slots=True)
class Hatch2D:
    boundary: Profile2D | ClosedCurve2D
    layer: str
    pattern: str = "ANSI31"
    angle: float = 45.0
    scale: float = 1.0

@dataclass(frozen=True, slots=True)
class Insert2D: ...
```

### `src/cady/drawing/dimensions.py`

```python
@dataclass(frozen=True, slots=True)
class DimStyle: ...
@dataclass(frozen=True, slots=True)
class LinearDimension2D: ...
@dataclass(frozen=True, slots=True)
class AlignedDimension2D: ...
@dataclass(frozen=True, slots=True)
class RadiusDimension2D: ...
@dataclass(frozen=True, slots=True)
class DiameterDimension2D: ...
@dataclass(frozen=True, slots=True)
class AngularDimension2D: ...
```

### `src/cady/drawing/document.py`

```python
@dataclass(frozen=True, slots=True)
class Drawing2D:
    name: str = "drawing"
    units: str = "m"
    layers: tuple[Layer, ...] = ()
    entities: tuple[DrawingEntity | Text2D | Hatch2D | Insert2D | Dimension2D, ...] = ()
    blocks: tuple[BlockDefinition, ...] = ()
    dim_styles: tuple[DimStyle, ...] = ()
    header: Mapping[str, int | float | str] = field(default_factory=dict)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def add(self, geometry, *, layer: str = "0") -> Drawing2D: ...
    def add_layer(self, layer: Layer | str, *, color: int = 7, linetype: str = "CONTINUOUS") -> Drawing2D: ...
    def add_text(...) -> Drawing2D: ...
    def hatch(...) -> Drawing2D: ...
    def add_dimension(...) -> Drawing2D: ...
    def bounds(self) -> tuple[Vec2, Vec2]: ...
    def to_arrays(self, *, tolerance: float) -> tuple[object, ...]: ...
```

## Product

### `src/cady/product/material.py`

```python
@dataclass(frozen=True, slots=True)
class Material:
    name: str
    density: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
```

### `src/cady/product/part.py`

```python
@dataclass(frozen=True, slots=True)
class Part:
    name: str
    bodies: tuple[Body3D, ...] = ()
    material: Material | None = None
    display_style: DisplayStyle | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def with_body(self, body: Body3D) -> Part: ...
    def to_mesh(self, *, tolerance: float) -> Mesh3D: ...
```

### `src/cady/product/assembly.py`

```python
@dataclass(frozen=True, slots=True)
class PartInstance:
    name: str
    part: Part
    pose: Pose3D = field(default_factory=Pose3D.identity)

@dataclass(frozen=True, slots=True)
class AssemblyInstance:
    name: str
    assembly: Assembly
    pose: Pose3D = field(default_factory=Pose3D.identity)

@dataclass(frozen=True, slots=True)
class Assembly:
    name: str
    instances: tuple[PartInstance | AssemblyInstance, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def add(self, target: Part | Assembly, *, name: str, pose: Pose3D | None = None) -> Assembly: ...
    def flatten(self) -> tuple[PlacedPart, ...]: ...
    def to_mesh(self, *, tolerance: float) -> Mesh3D: ...
```

## View

### `src/cady/view/style.py`

```python
@dataclass(frozen=True, slots=True)
class DisplayStyle:
    color: tuple[float, float, float] | None = None
    alpha: float = 1.0
    visible_edges: bool = False
```

### `src/cady/view/camera.py`

```python
Projection = Literal["perspective", "orthographic"]

@dataclass(frozen=True, slots=True)
class Camera:
    name: str = "camera"
    projection: Projection = "perspective"
    position: Vec3 = Vec3(0, -10, 5)
    target: Vec3 = Vec3(0, 0, 0)
    up: Vec3 = Vec3(0, 0, 1)
    fov_degrees: float = 35.0
    orthographic_scale: float | None = None
    near: float = 0.01
    far: float = 1_000_000.0

    @classmethod
    def look_at(cls, *, position, target, up=(0, 0, 1), fov_degrees=35.0, name="camera") -> Camera: ...
```

### `src/cady/view/light.py`

```python
@dataclass(frozen=True, slots=True)
class AmbientLight: ...
@dataclass(frozen=True, slots=True)
class DirectionalLight: ...
@dataclass(frozen=True, slots=True)
class PointLight: ...
Light = AmbientLight | DirectionalLight | PointLight
```

### `src/cady/view/scene.py`

```python
SceneTarget = Drawing2D | Body3D | Part | Assembly | Mesh3D

@dataclass(frozen=True, slots=True)
class SceneObject:
    name: str
    target: SceneTarget
    pose: Pose3D = field(default_factory=Pose3D.identity)
    visible: bool = True
    display_style: DisplayStyle | None = None

@dataclass(frozen=True, slots=True)
class Scene:
    name: str = "scene"
    objects: tuple[SceneObject, ...] = ()
    cameras: tuple[Camera, ...] = ()
    active_camera: str | None = None
    lights: tuple[Light, ...] = ()
    default_style: DisplayStyle | None = None

    @classmethod
    def from_target(cls, target: SceneTarget, *, name: str = "scene") -> Scene: ...
    @classmethod
    def from_assembly(cls, assembly: Assembly, *, name: str | None = None) -> Scene: ...
    def add(self, target: SceneTarget, *, name: str | None = None, pose: Pose3D | None = None) -> Scene: ...
    def with_camera(self, camera: Camera, *, active: bool = True) -> Scene: ...
    def with_light(self, light: Light) -> Scene: ...
```

## Document

### `src/cady/document.py`

```python
@dataclass(frozen=True, slots=True)
class Document:
    name: str
    units: str = "m"
    drawings: tuple[Drawing2D, ...] = ()
    parts: tuple[Part, ...] = ()
    assemblies: tuple[Assembly, ...] = ()
    scenes: tuple[Scene, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def with_drawing(self, drawing: Drawing2D) -> Document: ...
    def with_part(self, part: Part) -> Document: ...
    def with_assembly(self, assembly: Assembly) -> Document: ...
    def with_scene(self, scene: Scene) -> Document: ...
```

## File Facades

### `src/cady/files/dxf/__init__.py`

```python
@dataclass(frozen=True, slots=True)
class DxfImportResult:
    drawing: Drawing2D | None = None
    meshes: tuple[Mesh3D, ...] = ()
    wires: tuple[Polyline3D, ...] = ()
    skipped: tuple[DxfSkippedEntity, ...] = ()

def read(path: str | Path) -> DxfImportResult: ...
def read_drawing(path: str | Path) -> Drawing2D: ...
def read_mesh(path: str | Path) -> Mesh3D: ...
def render(drawing: Drawing2D, *, tolerance: float) -> str: ...
def write(drawing: Drawing2D, path: str | Path, *, tolerance: float) -> Drawing2D: ...
```

### `src/cady/files/stl/__init__.py`

```python
StlTarget = Mesh3D | Body3D | Part | Assembly | Document
def write(target: StlTarget, path: str | Path, *, ascii: bool = False, tolerance: float) -> StlTarget: ...
```

### `src/cady/files/step/__init__.py`

```python
StepTarget = Body3D | Part | Assembly | Document
def render(target: StepTarget, *, name: str | None = None) -> str: ...
def write(target: StepTarget, path: str | Path, *, name: str | None = None) -> StepTarget: ...
def read_faces(path: str | Path) -> list[StepFace]: ...
def read_members(path: str | Path) -> list[ExtrudedMember]: ...
```
