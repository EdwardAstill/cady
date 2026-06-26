# View and Visualisation Unification Tasks

1. Move implementation modules into `src/cady/view/`.
   - Verification: `PYTHONPATH=src .venv/bin/python -c "from cady.view.vispy_viewer import prepare_scene; print(prepare_scene.__name__)"`

2. Add lazy viewer exports to `cady.view` and remove the old separate package.
   - Verification: `PYTHONPATH=src .venv/bin/python -c "from cady.view import view_scene; import pathlib; print(view_scene.__name__, pathlib.Path('src/cady/visualisation').exists())"`

3. Update object view helpers and tests to use `cady.view` as canonical.
   - Verification: `PYTHONPATH=src .venv/bin/pytest -q tests/view/test_object_view_methods.py tests/view/test_vispy_viewer.py`

4. Update examples and docs away from the old package imports.
   - Verification: `rg -n "from cady\\.visualisation|cady\\.visualisation|visualisation module" README.md docs examples tests src/cady`

5. Run targeted gates and final hygiene checks.
   - Verification: `PYTHONPATH=src .venv/bin/pytest -q tests/view tests/examples/test_visualise_3d.py tests/conventions/test_import_boundaries.py tests/conventions/test_stdlib_only.py`
   - Verification: `git diff --check`
   - Verification: `git status --short`
