# cady.view Package

`cady.view` is the backend-independent scene layer plus the optional VisPy
viewer. Importing `cady.view` should stay lightweight: GUI backend imports are
kept behind the viewer launch path.

## Main Flow

1. User code builds a `Scene` directly, calls `Scene.from_target(...)`, or uses
   a target `.view(...)` method.
2. `scene.prepare_scene(...)` converts semantic targets into `RenderScene`
   arrays: `SceneMesh` for mesh and point data, `SceneLine` for polyline data,
   plus camera and lighting values.
3. `viewer.view_scene(...)` launches the VisPy path only when requested.
4. `vispy.draw_batches.build_canvas_geometry(...)` converts `RenderScene` data
   into GPU-ready draw batches and viewer bounds.
5. `vispy.canvas._make_vispy_canvas(...)` creates the interactive canvas, draws
   face, explicit/wireframe edge, point, and opt-in overlay batches, and
   delegates camera motion to `vispy.interaction`.

## Top-Level Files

- `__init__.py`
  - Public facade for backend-independent values such as `Scene`, `Camera`,
    `DisplayStyle`, lights, overlays, and `prepare_scene`.
  - Lazily exposes GUI helpers (`view_scene`, `view_lines`) through
    `__getattr__` so importing the package does not require VisPy.

- `camera.py`
  - Defines `Camera` and its `Projection` modes.
  - Validates finite camera vectors, non-degenerate view/up bases, clipping
    planes, perspective FOV, orthographic scale, and zoom limits.
  - Provides constructors for explicit look-at, perspective, and orthographic
    cameras.

- `errors.py`
  - Re-exports the shared `ViewError` type for the view package.

- `light.py`
  - Defines immutable light values: `Light`, `AmbientLight`,
    `DirectionalLight`, and `PointLight`.
  - Validates light intensity, RGB colors, directional vectors, and point-light
    ranges.

- `overlay.py`
  - Defines backend-independent overlay settings.
  - `ScaleBarOverlay` controls orthographic scale-bar visibility, color, and
    pixel limits.
  - `LocalAxesOverlay` controls the local X/Y/Z axes marker colors and
    visibility.

- `scene.py`
  - Owns the backend-independent scene graph: `SceneObject` and `Scene`.
  - Defines prepared render payloads: `RenderScene`, `SceneMesh`, and
    `SceneLine`.
  - Converts scene targets into renderable arrays in `prepare_scene(...)`.
    Point clouds and explicit polylines are handled before mesh conversion.
  - Applies scene-object poses, resolves display colors, and reduces scene
    lights to the ambient/directional values used by the current shader.
  - Defaults to one restrained ambient light, one directional light, and no
    overlays. Overlays remain available when a caller explicitly requests them.

- `style.py`
  - Defines `DisplayStyle` and `RenderMode` (`shaded`, `wireframe`, `points`).
  - Carries object-level rendering hints such as color, opacity, line width,
    point size, visibility, and metadata.
  - Provides `style_from_mapping(...)` for plain data inputs.

- `viewer.py`
  - Public launch helpers for interactive viewing.
  - `view_scene(...)` opens a prepared `Scene`.
  - `view_lines(...)` renders explicit polylines without meshing.
  - `open_target_view(...)` is the fitted-camera path used by target `.view(...)`
    methods. It resolves bounds, optional centering, default style, and default
    camera before calling the public `view_scene` helper.

## `vispy/` Backend Files

- `vispy/__init__.py`
  - Empty backend package marker. Public viewer helpers are exposed from the
    top-level `cady.view` facade instead.

- `vispy/canvas.py`
  - Imports VisPy only inside the canvas creation path.
  - Defines a small ambient-plus-directional shader and the
    `_make_vispy_canvas(...)` factory. There are no shadow, specular, or material
    passes.
  - The inner `VispyCanvas` owns GL state, projection/model/view matrices,
    draw order, mouse interaction, wheel zoom, keyboard shortcuts, and overlay
    drawing.
  - Draw order is faces first, then edges, points, local axes, and scale bar.

- `vispy/draw_batches.py`
  - Converts `RenderScene` meshes and lines into `DrawBatch` values.
  - Builds separate face, edge, and point batches for the canvas. Shaded meshes
    only draw semantic display edges; wireframe meshes derive raw triangle edges
    when no explicit edges exist.
  - Computes `SceneBounds`, which drive orbit center, clipping radius, and
    overlay sizing.

- `vispy/interaction.py`
  - Owns viewer-space matrix math and interactive camera state.
  - `ViewerInteractionState` tracks distance, pan, orientation, orthographic
    scale, and the declared camera target used as the orbit center.
  - Handles orbit, pan, zoom, local axis length, projection clip planes, and
    numeric-key orientation shortcuts.

- `vispy/mesh_buffers.py`
  - Builds view-only mesh buffers for flat shaded rendering.
  - `flat_face_buffers(...)` duplicates each triangle's vertices and assigns one
    normal per face for flat shading.
  - This operation does not mutate or simplify the source `Mesh3`.

- `vispy/overlays.py`
  - Implements VisPy renderers for `ScaleBarOverlay` and `LocalAxesOverlay`.
  - Scale bars are shown only for orthographic cameras, where one stable
    world-units-per-pixel scale exists.
  - Local axes are drawn in scene space near the local center and scaled relative
    to the viewport.

## Boundaries To Preserve

- Keep `cady.view` importable without VisPy, PyQt, or OpenGL installed.
- Keep semantic scene values immutable; return new values from modifiers such as
  `Scene.add(...)`, `Scene.with_overlay(...)`, and `DisplayStyle.with_metadata(...)`.
- Keep mesh conversion explicit and pass `tolerance` through the viewer boundary.
- Keep backend-specific rendering code under `vispy/`; backend-independent
  scene, camera, style, light, and overlay values stay at the top level.
