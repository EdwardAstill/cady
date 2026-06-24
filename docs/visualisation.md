# Visualisation

cady's core visual model is backend-independent. The `cady.view` package stores
scene descriptions: targets, cameras, lights, display styles, object poses, and
metadata. It does not render anything by itself.

## Scene values

```python
from cady import Camera, DirectionalLight, DisplayStyle, Scene

scene = (
    Scene("review")
    .add(part, style=DisplayStyle(color=(0.74, 0.78, 0.82), render_mode="shaded"))
    .with_camera(
        Camera.perspective(
            position=(1.7, -1.6, 0.9),
            target=(0.5, 0.3, 0.05),
            fov_degrees=35.0,
        ),
        name="iso",
    )
    .with_light(DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.6))
)
```

Scenes can reference bodies, parts, assemblies, meshes, drawings, or imported
wire data. They do not own CAD geometry and they do not affect file export.

## Cameras, lights, and styles

Camera constructors:

- `Camera.look_at(position=..., target=..., up=(0, 0, 1))`
- `Camera.perspective(position=..., target=..., up=(0, 0, 1), fov_degrees=45.0)`
- `Camera.orthographic(position=..., target=..., up=(0, 0, 1), scale=1.0)`

Light values:

- `AmbientLight(intensity=..., color=(1, 1, 1))`
- `DirectionalLight(direction=..., intensity=..., color=(1, 1, 1))`
- `PointLight(position=..., intensity=..., color=(1, 1, 1), range=None)`

Display styles support color, opacity, line width, point size, visibility, and
`render_mode` values of `"shaded"`, `"wireframe"`, and `"points"`.

## VisPy viewer

Install the optional viewer dependencies with `cady[visualisation]`. The VisPy
adapter consumes the backend-independent `Scene`, `Camera`, `Light`, and
`DisplayStyle` values:

```python
from cady.visualisation import view_scene

view_scene(scene, tolerance=1e-3)
```

`examples/scripts/visualise_3d.py` opens a VisPy window for the selected target:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3d.py --shape plate
```

3D objects also expose a convenience `view(...)` method. It builds a scene with
a fitted camera, a default light, and a default display style, then opens that
scene:

```python
mesh.view(title="review")
body.view(render_mode="wireframe")
part.view(color=(0.7, 0.75, 0.82))
assembly.view(projection="perspective")
```

Pass `camera=...`, `style=...`, `light=...`, `name=...`, `title=...`,
`render_mode=...`, `color=...`, `projection=...`, `center=...`, or
`tolerance=...` when the defaults are not enough. These methods return `None`.

`examples/scripts/visualise_plate.py` writes a scene summary text file and the
same plate as DXF/STL:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_plate.py --out /tmp/cady-visualisation
```

## Optional visualisation package

`cady.visualisation` provides scene construction and VisPy viewing helpers:

```python
from cady.visualisation import scene_from_target, view_target

scene = scene_from_target(part, name="review")
view_target(part)
```

Rendering adapters remain leaf code. Core packages must not import viewer
libraries at module scope.
