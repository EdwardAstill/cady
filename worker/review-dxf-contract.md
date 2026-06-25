## Review

- Correct: `DxfImportResult.wires` is removed from the Python runtime contract. `DxfImportResult` now has `wireframes: tuple[Wireframe3D, ...]` and no `wires` slot (`src/cady/files/dxf/__init__.py:25-30`); `tests/files/test_new_file_facades.py:106-114` asserts `result.wireframes` contents and `not hasattr(result, "wires")`.
- Correct: `DxfImportResult.wireframes` is populated as `Wireframe3D` objects from 3D `POLYLINE` entities. `_parse_meshes` builds sequential edges and appends `Wireframe3D(tuple(vertices), edges)` (`src/cady/files/dxf/__init__.py:297-308`). Targeted test coverage verifies vertices and edges through `dxf.read_wireframe` (`tests/geometry3d/test_mesh.py:88-148`).
- Correct: `dxf.read_wireframe(path)` exists, is exported, and merges imported wireframes with index offsets (`src/cady/files/dxf/__init__.py:66-81`, `src/cady/files/dxf/__init__.py:475-482`). Manual verification on a wire-only temp DXF returned 2 vertices and edge `((0, 1),)`.
- Correct: `dxf.read_mesh(path)` now rejects wire-only DXF files because it only accepts `result.meshes` and raises `ReadError` when that tuple is empty (`src/cady/files/dxf/__init__.py:59-63`). Manual verification on a wire-only temp DXF raised `ReadError: DXF contained no supported mesh geometry`.
- Correct: Required searches over `src/` and `tests/` found no remaining Python call sites for `result.wires`, `.wires`, or `Mesh3D.from_dxf`. `Mesh3D.from_dxf` removal is also asserted by `tests/geometry3d/test_mesh.py:187-188`.
- Correct: The primary linesplan scripts use the new API: `examples/linesplan/visualise_linesplan_9m.py:27-35` uses `result.wireframes`/`dxf.read_wireframe`, and `examples/linesplan/mirror-mesh.py:60-63` uses `dxf.read_wireframe`. `mirror-mesh.py --no-view` ran successfully.

- Blocker: `examples/linesplan/close-mirror-mesh.py` is currently broken with the real linesplan input. It uses the new API (`dxf.read_wireframe` at `examples/linesplan/close-mirror-mesh.py:72`), but `--no-view` fails at `mirrored.close_planar(...)` (`examples/linesplan/close-mirror-mesh.py:83-84`) with `ValueError: Could not triangulate cap loop; try cap=False`. This violates the linesplan example acceptance path in `.plans/wireframe-type/plan.md` and leaves one linesplan script non-working.

- Note: Whole-repo documentation still contains stale contract references even though Python source/tests are clean: `docs/files/dxf-format-cheatsheet.md:238-239` says `DxfImportResult.wires`, `docs/files/index.md:41-46` lists `wires`, and `examples/README.md:34-36` references `Mesh3D.from_dxf(...)` and the old examples path. Severity: Medium (documentation/API contract drift).
- Note: Existing committed tests do not include an assertion that `dxf.read_mesh(...)` rejects a wire-only DXF; only manual verification covered this during review. Severity: Low (test coverage gap), because the implementation behavior is correct.
- Note: Requested `/home/eastill/projects/cady/plan.md` and `/home/eastill/projects/cady/progress.md` were not present. I reviewed `.plans/wireframe-type/plan.md` as the relevant plan; no `progress.md` was found.

## Evidence

Commands run:

- `git status --short && git diff --stat && git diff -- src tests examples` — inspected current diff summary and relevant changes.
- `rg "result\.wires" src/ tests/ --type py || true` — no matches.
- `rg "Mesh3D\.from_dxf" src/ tests/ --type py || true` — no matches.
- `rg "\.wires" src/cady/ tests/ --type py || true` — no matches.
- `rg "result\.wires|Mesh3D\.from_dxf|\.wires" src/ tests/ examples/ --type py || true` — no Python matches in source/tests/examples.
- `rg "result\.wires|Mesh3D\.from_dxf|\.wires|\bwires\b|wireframes" -n . --glob '!worker/**' --glob '!*.dxf' --glob '!*.stl' || true` — found stale docs/README references listed above.
- `PYTHONPATH=src .venv/bin/python - <<'PY' ... PY` — manually verified wire-only DXF: `result.wireframes == 1`, `result.meshes == 0`, `hasattr(result, "wires") == False`, `read_wireframe` works, `read_mesh` rejects.
- `PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py tests/geometry3d/test_mesh.py tests/geometry3d/test_wireframe.py tests/examples/test_visualise_3d.py` — 36 passed.
- `PYTHONPATH=src .venv/bin/python examples/linesplan/mirror-mesh.py --no-view && PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py --no-view` — first script passed; second script failed with the blocker above.
- `git diff --check && git status --short worker/review-dxf-contract.md` — no whitespace errors before writing this report.
- `git diff --cached --name-only` — no staged files.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Concrete findings above include file:line references and severity for the broken linesplan close script, stale docs/API references, and the read_mesh wire-only test coverage gap."
    }
  ],
  "changedFiles": [],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "git status --short && git diff --stat && git diff -- src tests examples",
      "result": "passed",
      "summary": "Inspected current git diff and relevant changed files."
    },
    {
      "command": "rg \"result\\.wires\" src/ tests/ --type py || true; rg \"Mesh3D\\.from_dxf\" src/ tests/ --type py || true; rg \"\\.wires\" src/cady/ tests/ --type py || true",
      "result": "passed",
      "summary": "No required-search matches in Python source/tests."
    },
    {
      "command": "rg \"result\\.wires|Mesh3D\\.from_dxf|\\.wires\" src/ tests/ examples/ --type py || true",
      "result": "passed",
      "summary": "No old Python call sites in source/tests/examples."
    },
    {
      "command": "rg \"result\\.wires|Mesh3D\\.from_dxf|\\.wires|\\bwires\\b|wireframes\" -n . --glob '!worker/**' --glob '!*.dxf' --glob '!*.stl' || true",
      "result": "passed",
      "summary": "Found stale docs/README references to old wires/from_dxf contract."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/python - <<'PY' ... PY",
      "result": "passed",
      "summary": "Manual wire-only DXF check: read_wireframe worked and read_mesh raised ReadError."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py tests/geometry3d/test_mesh.py tests/geometry3d/test_wireframe.py tests/examples/test_visualise_3d.py",
      "result": "passed",
      "summary": "36 targeted tests passed."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/python examples/linesplan/mirror-mesh.py --no-view && PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py --no-view",
      "result": "failed",
      "summary": "mirror-mesh passed; close-mirror-mesh failed at close_planar with ValueError: Could not triangulate cap loop."
    },
    {
      "command": "git diff --check && git status --short worker/review-dxf-contract.md",
      "result": "passed",
      "summary": "No diff whitespace errors before writing report."
    },
    {
      "command": "git diff --cached --name-only",
      "result": "passed",
      "summary": "No staged files."
    }
  ],
  "validationOutput": [
    "Required rg searches over src/tests returned no matches.",
    "Manual wire-only DXF output: wireframes 1 meshes 0 has_wires False; read_wireframe vertices 2 edges ((0, 1),); read_mesh rejected DXF contained no supported mesh geometry.",
    "Targeted pytest output: 36 passed in 0.83s.",
    "close-mirror-mesh.py --no-view failed with ValueError: Could not triangulate cap loop; try cap=False."
  ],
  "residualRisks": [
    "Stale docs/README references to DxfImportResult.wires and Mesh3D.from_dxf remain outside Python source/tests.",
    "No committed test currently asserts dxf.read_mesh rejects a wire-only DXF; this was manually verified only.",
    "Exact requested plan.md/progress.md paths were missing; reviewed .plans/wireframe-type/plan.md instead."
  ],
  "noStagedFiles": true,
  "notes": "No project/source files were modified; this worker report was written to worker/review-dxf-contract.md as requested."
}
```
