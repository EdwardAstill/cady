# View and Visualisation Unification Spec

## Goal

Combine the public view and visualisation surfaces so `cady.view` is the
canonical package for scene values, scene preparation, and optional interactive
viewing.

## Actual Audit

Current modules:

- `src/cady/view/*` owns `Scene`, `SceneObject`, `Camera`, `Light`,
  `DisplayStyle`, `ViewError`, and `.view()` scene construction helpers.
- The former separate viewer package owned `PreparedScene`, `SceneMesh`,
  `SceneLine`, mesh buffer helpers, and VisPy viewer functions.
- `src/cady/view/open_view.py` called back into that old package, which made it
  the runtime viewer entry point.
- Examples, tests, and docs import `prepare_scene` and `view_scene` from
  the old package.

Comparison:

- Optimal: scene/value types are already independent from GUI libraries.
- Close: viewer imports are lazy with respect to VisPy itself.
- Different: the public API was split between scene values and viewer helpers,
  and object `.view()` methods called the old package.
- Dead: the separate viewer package is removed after moving its implementation
  into `cady.view`.

## Target Changes

- Move `mesh_buffers.py` and `vispy_viewer.py` implementation under
  `src/cady/view/`.
- Update internal imports so `open_target_view()` calls canonical
  `cady.view.view_scene`.
- Add lazy viewer re-exports to `src/cady/view/__init__.py`:
  `PreparedScene`, `SceneLine`, `SceneMesh`, `prepare_scene`, `view_scene`,
  `view_target`, `view_mesh`, `view_meshes`, and `view_lines`.
- Add `scene_from_target()` to `cady.view`.
- Remove the old separate viewer package after moving its implementation into
  `cady.view`.
- Update tests, examples, and docs to use `cady.view` as the canonical import
  path.

## Done Criteria

- `from cady.view import prepare_scene, view_scene, view_target` works.
- The old separate viewer package no longer exists.
- Object `.view()` methods can be monkeypatched via `cady.view.view_scene`.
- Importing `cady.view` does not import VisPy.
- Existing view and visualisation behavior tests pass.
- `git diff --check` passes.
