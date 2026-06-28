from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cady import (
    Assembly,
    Body3,
    Camera,
    DirectionalLight,
    DisplayStyle,
    Document,
    Drawing2,
    Part,
    Region2,
    Scene,
    circle2,
    line2,
    region_rectangle,
)
from cady.view import SceneObject

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"

PLATE_WIDTH = 1.0
PLATE_HEIGHT = 0.6
PLATE_THICKNESS = 0.04
HOLE_CENTRE = (0.5, 0.3)
HOLE_RADIUS = 0.12


@dataclass(frozen=True, slots=True)
class PlateExample:
    drawing: Drawing2
    part: Part
    region: Region2


def plate_region() -> Region2:
    outline = region_rectangle(PLATE_WIDTH, PLATE_HEIGHT)
    hole = circle2(HOLE_CENTRE, HOLE_RADIUS)
    return Region2(outline.outer, holes=(hole,))


def plate_body() -> Body3:
    return Body3.from_region(plate_region()).extrude(PLATE_THICKNESS)


def plate_part(*, name: str = "plate") -> Part:
    return Part(name).with_body(plate_body())


def plate_drawing(*, name: str = "front", title: str = "PLATE") -> Drawing2:
    region = plate_region()
    hole = region.holes[0]
    return (
        Drawing2(name)
        .add_layer("PLATE", color=7)
        .add_layer("CENTER", color=3, linetype="CENTER")
        .add_layer("TEXT", color=2)
        .add(region.outer, layer="PLATE")
        .add(hole, layer="PLATE")
        .add(line2((0.5, 0.05), (0.5, 0.55)), layer="CENTER")
        .add(line2((0.38, 0.3), (0.62, 0.3)), layer="CENTER")
        .add_text(title, at=(0.02, 0.02), height=0.03, layer="TEXT")
    )


def production_drawing() -> Drawing2:
    return (
        plate_drawing(name="production_plate", title="PRODUCTION PLATE")
        .add_layer("SYMBOL", color=2)
        .add(circle2((0.5, 0.3), 0.025), layer="SYMBOL")
        .add(circle2((0.82, 0.3), 0.025), layer="SYMBOL")
        .add(line2((0.0, -0.08), (1.0, -0.08)), layer="PLATE")
        .add(line2((1.08, 0.0), (1.08, 0.6)), layer="PLATE")
    )


def plate_example() -> PlateExample:
    return PlateExample(
        drawing=plate_drawing(),
        part=plate_part(),
        region=plate_region(),
    )


def plate_document(*, name: str = "model_plate") -> Document:
    example = plate_example()
    return (
        Document(name)
        .add_drawing(example.drawing, name="front")
        .add_part(example.part, name=example.part.name)
    )


def production_assembly() -> Assembly:
    pin = Part("pin").with_body(Body3.box(width=0.1, depth=0.1, height=0.08))
    return (
        Assembly("production_plate")
        .add(plate_part(), name="plate")
        .add(pin, name="pin", pose=(0.45, 0.25, PLATE_THICKNESS))
    )


def scene_for_target(target: object, *, name: str = "scene") -> Scene:
    return (
        Scene(name=name)
        .add(
            target,
            style=DisplayStyle(color=(0.74, 0.78, 0.82), render_mode="shaded"),
        )
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


def scene_summary(scene: Scene) -> str:
    lines = [
        f"scene: {scene.name}",
        f"objects: {len(scene.objects)}",
        f"cameras: {', '.join(name for name, _camera in scene.cameras) or 'none'}",
        f"active_camera: {scene.active_camera or 'none'}",
        f"lights: {len(scene.lights)}",
    ]
    for item in scene.objects:
        lines.append(_object_summary(item))
    return "\n".join(lines) + "\n"


def _object_summary(item: SceneObject) -> str:
    style = item.style.render_mode if item.style is not None else "default"
    return f"- {item.object_name}: {type(item.target).__name__}, style={style}"
