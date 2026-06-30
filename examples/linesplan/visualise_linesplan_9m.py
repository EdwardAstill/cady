"""Visualise the 9m linesplan DXF wireframe.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan/visualise_linesplan_9m.py
"""

from __future__ import annotations

from pathlib import Path

from cady import Camera, DirectionalLight, DisplayStyle, Scene, Wireframe3
from cady.files import dxf
from cady.operations import Transform3
from cady.view import Camera as CameraType
from cady.view import view_scene

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
WIRE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe")
MESH_STYLE = DisplayStyle(color=(0.62, 0.68, 0.72), render_mode="wireframe")
PROFILE_LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)


def main() -> None:
    result = dxf.read(LINESPLAN_DXF)
    _reject_empty_linesplan(result)

    wire_scene = build_wire_scene(result)
    print_wire_summary(result, wire_scene)
    view_scene(wire_scene, title="linesplan 9m - DXF wires")

    wf = dxf.read_wireframe(LINESPLAN_DXF)
    print_wireframe_summary(wf)
    wf.view(title="linesplan 9m - Wireframe3", style=MESH_STYLE)


def build_wire_scene(result: dxf.DxfImportResult) -> Scene:
    lower, upper = _result_bounds(result)
    centre = _bounds_centre(lower, upper)
    origin_pose = Transform3().translate(-centre[0], -centre[1], -centre[2])
    camera = _fit_profile_camera(lower, upper)
    scene = Scene(name="linesplan_9m_wires", camera=camera, lights=(PROFILE_LIGHT,))

    for index, wf in enumerate(result.wireframes, start=1):
        scene = scene.add(
            wf,
            name=f"wireframe_{index}",
            pose=origin_pose,
            style=WIRE_STYLE,
        )

    for index, mesh in enumerate(result.meshes, start=1):
        scene = scene.add(
            mesh,
            name=f"mesh_{index}",
            pose=origin_pose,
            style=MESH_STYLE,
        )

    return scene


def print_wire_summary(result: dxf.DxfImportResult, scene: Scene) -> None:
    print(
        f"loaded {len(result.wireframes)} wireframes and {len(result.meshes)} meshes "
        f"from {LINESPLAN_DXF}"
    )
    if result.skipped:
        print(f"skipped {len(result.skipped)} unsupported 3D DXF entities")

    camera = scene.camera
    print(f"scene objects: {len(scene.objects)}")
    print(f"camera: {camera.projection}")
    print(f"camera target: {camera.target}")
    print(f"camera scale: {camera.orthographic_scale:g}")


def print_wireframe_summary(wf: Wireframe3) -> None:
    print(f"wireframe vertices: {len(wf.vertices)}")
    print(f"wireframe edges: {len(wf.edges)}")


def _reject_empty_linesplan(result: dxf.DxfImportResult) -> None:
    if not result.wireframes and not result.meshes:
        raise SystemExit(f"{LINESPLAN_DXF} contains no supported DXF 3D wires or meshes")


def _fit_profile_camera(
    lower: tuple[float, float, float],
    upper: tuple[float, float, float],
) -> CameraType:
    span = (upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2])
    profile_scale = max(span[2], span[0] / VIEW_ASPECT, 1.0) * FIT_PADDING
    distance = max(span) * 1.5 or 1.0
    return Camera.orthographic(
        position=(0.0, -distance, 0.0),
        target=(0.0, 0.0, 0.0),
        scale=profile_scale,
    )


def _result_bounds(
    result: dxf.DxfImportResult,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for wf in result.wireframes:
        lower, upper = wf.bounds()
        points.extend((_point_tuple(lower), _point_tuple(upper)))
    for mesh in result.meshes:
        lower, upper = mesh.bounds()
        points.extend((_point_tuple(lower), _point_tuple(upper)))
    if not points:
        raise ValueError("cannot fit an empty linesplan scene")
    return (
        (
            min(point[0] for point in points),
            min(point[1] for point in points),
            min(point[2] for point in points),
        ),
        (
            max(point[0] for point in points),
            max(point[1] for point in points),
            max(point[2] for point in points),
        ),
    )


def _bounds_centre(
    lower: tuple[float, float, float],
    upper: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )


def _point_tuple(value: object) -> tuple[float, float, float]:
    point = value.tuple() if hasattr(value, "tuple") else value
    x, y, z = point
    return (float(x), float(y), float(z))


if __name__ == "__main__":
    main()
