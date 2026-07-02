"""Overlay renderers for the VisPy viewer backend."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, log10
from typing import Any

import numpy as np

from cady.view.camera import Camera
from cady.view.overlay import LocalAxesOverlay, ScaleBarOverlay
from cady.view.scene import RenderScene
from cady.view.vispy.draw_batches import index_buffer, solid_color_vertices

LOCAL_AXIS_COLORS: tuple[tuple[float, float, float], ...] = (
    (0.9, 0.05, 0.05),
    (0.05, 0.62, 0.18),
    (0.1, 0.28, 0.95),
)
SCALE_BAR_COLOR = (0.05, 0.06, 0.07)
SCALE_BAR_MAX_PIXELS = 140.0
SCALE_BAR_MIN_PIXELS = 36.0
SCALE_BAR_MARGIN_PIXELS = 24.0
SCALE_BAR_BOTTOM_PIXELS = 38.0
SCALE_BAR_TEXT_BOTTOM_PIXELS = 18.0
SCALE_BAR_TICK_PIXELS = 10.0


@dataclass(frozen=True, slots=True)
class ScaleBar:
    exponent: int
    length_units: float
    width_pixels: float
    label: str


def scale_bar_overlay(prepared: RenderScene) -> ScaleBarOverlay | None:
    for overlay in prepared.overlays:
        if isinstance(overlay, ScaleBarOverlay) and overlay.visible:
            return overlay
    return None


def local_axes_overlay(prepared: RenderScene) -> LocalAxesOverlay | None:
    for overlay in prepared.overlays:
        if isinstance(overlay, LocalAxesOverlay) and overlay.visible:
            return overlay
    return None


def scale_bar_label(exponent: int) -> str:
    if exponent == 0:
        return "1 unit"
    return f"1e{exponent} units"


def scale_bar_for_visible_height(
    visible_world_height: float,
    viewport_size: tuple[int, int],
    *,
    min_pixels: float = SCALE_BAR_MIN_PIXELS,
    max_pixels: float = SCALE_BAR_MAX_PIXELS,
) -> ScaleBar:
    _width, height = viewport_size
    height_px = max(float(height), 1.0)
    units_per_pixel = max(float(visible_world_height), 1e-12) / height_px
    exponent = floor(log10(units_per_pixel * max_pixels))

    while (10.0**exponent) / units_per_pixel < min_pixels:
        exponent += 1

    length_units = 10.0**exponent
    return ScaleBar(
        exponent=exponent,
        length_units=length_units,
        width_pixels=length_units / units_per_pixel,
        label=scale_bar_label(exponent),
    )


def scale_bar_visible_height(
    camera: Camera,
    *,
    distance: float,
    orthographic_scale: float,
) -> float | None:
    if camera.projection == "orthographic":
        return max(float(orthographic_scale), 1e-12)
    # Perspective views do not have one stable world-units-per-pixel scale.
    return None


def scale_bar_for_camera(
    camera: Camera,
    *,
    distance: float,
    orthographic_scale: float,
    viewport_size: tuple[int, int],
    min_pixels: float = SCALE_BAR_MIN_PIXELS,
    max_pixels: float = SCALE_BAR_MAX_PIXELS,
) -> ScaleBar | None:
    visible_height = scale_bar_visible_height(
        camera,
        distance=distance,
        orthographic_scale=orthographic_scale,
    )
    if visible_height is None:
        return None
    return scale_bar_for_visible_height(
        visible_height,
        viewport_size,
        min_pixels=min_pixels,
        max_pixels=max_pixels,
    )


def scale_bar_line_vertices(
    scale_bar: ScaleBar,
    viewport_size: tuple[int, int],
) -> np.ndarray:
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    usable_width = max(width_px - SCALE_BAR_MARGIN_PIXELS * 2.0, 1.0)
    bar_width = min(scale_bar.width_pixels, usable_width)
    x0 = SCALE_BAR_MARGIN_PIXELS
    x1 = x0 + bar_width
    y0 = min(SCALE_BAR_BOTTOM_PIXELS, height_px)
    y1 = min(y0 + SCALE_BAR_TICK_PIXELS, height_px)
    vertices = np.array(
        [
            (x0, y0),
            (x1, y0),
            (x0, y0),
            (x0, y1),
            (x1, y0),
            (x1, y1),
        ],
        dtype=np.float32,
    )
    # The overlay shader consumes clip-space positions, so pixel coordinates are
    # normalised here instead of going through the scene projection matrices.
    clip = np.empty_like(vertices)
    clip[:, 0] = (vertices[:, 0] / width_px) * 2.0 - 1.0
    clip[:, 1] = (vertices[:, 1] / height_px) * 2.0 - 1.0
    return np.ascontiguousarray(clip, dtype=np.float32)


def local_axis_line_data(
    origin: np.ndarray,
    length: float,
    colors: tuple[tuple[float, float, float], ...] = LOCAL_AXIS_COLORS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    basis = np.eye(3, dtype=np.float32) * np.float32(length)
    vertices: list[np.ndarray] = []
    axis_colors: list[tuple[float, float, float]] = []
    for axis_index, rgb in enumerate(colors):
        vertices.append(origin.astype(np.float32, copy=True))
        vertices.append((origin + basis[axis_index]).astype(np.float32, copy=False))
        axis_colors.extend((rgb, rgb))
    return (
        np.array(vertices, dtype=np.float32),
        np.array([[0, 1], [2, 3], [4, 5]], dtype=np.uint32),
        np.array(axis_colors, dtype=np.float32),
    )


@dataclass(slots=True)
class LocalAxesRenderer:
    positions: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    index_buffer: object
    local_centre: np.ndarray
    gloo: Any
    visible: bool = False

    @classmethod
    def create(
        cls,
        overlay: LocalAxesOverlay,
        *,
        local_centre: np.ndarray,
        gloo: Any,
    ) -> LocalAxesRenderer:
        colors = (overlay.x_color, overlay.y_color, overlay.z_color)
        positions, indices, axis_colors = local_axis_line_data(local_centre, 1.0, colors)
        _solid_positions, normals, _solid_colors = solid_color_vertices(
            positions,
            (0.0, 0.0, 0.0),
        )
        return cls(
            positions=np.ascontiguousarray(positions, dtype=np.float32),
            normals=normals,
            colors=np.ascontiguousarray(axis_colors, dtype=np.float32),
            index_buffer=index_buffer(indices, gloo),
            local_centre=local_centre,
            gloo=gloo,
            visible=overlay.visible,
        )

    def toggle(self) -> None:
        self.visible = not self.visible

    def update_length(self, length: float) -> None:
        positions, _indices, _colors = local_axis_line_data(self.local_centre, length)
        self.positions = np.ascontiguousarray(positions, dtype=np.float32)

    def draw(self, program: Any) -> None:
        if not self.visible:
            return
        self.gloo.set_state(
            blend=False,
            depth_test=False,
            depth_mask=False,
            polygon_offset_fill=False,
            line_width=3.0,
        )
        program["a_position"] = self.positions
        program["a_normal"] = self.normals
        program["a_color"] = self.colors
        program.draw("lines", self.index_buffer)


@dataclass(slots=True)
class ScaleBarRenderer:
    overlay: ScaleBarOverlay
    overlay_program: Any
    text_visual: Any
    positions: np.ndarray
    gloo: Any

    @classmethod
    def create(
        cls,
        overlay: ScaleBarOverlay,
        *,
        overlay_program: Any,
        visuals: Any,
        viewport_size: tuple[int, int],
        gloo: Any,
    ) -> ScaleBarRenderer:
        positions = scale_bar_line_vertices(
            scale_bar_for_visible_height(1.0, viewport_size),
            viewport_size,
        )
        text_visual = visuals.TextVisual(
            "1 unit",
            color=(*overlay.color, 1.0),
            font_size=11,
            pos=(SCALE_BAR_MARGIN_PIXELS, 0.0, 0.0),
            anchor_x="left",
            anchor_y="bottom",
            depth_test=False,
        )
        return cls(
            overlay=overlay,
            overlay_program=overlay_program,
            text_visual=text_visual,
            positions=positions,
            gloo=gloo,
        )

    def update(
        self,
        *,
        camera: Camera,
        distance: float,
        orthographic_scale: float,
        viewport_size: tuple[int, int],
        logical_size: tuple[int, int],
    ) -> None:
        scale_bar = scale_bar_for_camera(
            camera,
            distance=distance,
            orthographic_scale=orthographic_scale,
            viewport_size=viewport_size,
            min_pixels=self.overlay.min_pixels,
            max_pixels=self.overlay.max_pixels,
        )
        if scale_bar is None:
            return
        self.positions = scale_bar_line_vertices(scale_bar, viewport_size)
        self.text_visual.text = scale_bar.label

        width, height = viewport_size
        logical_width, logical_height = logical_size
        # VisPy line buffers use physical pixels, but TextVisual positions use
        # logical canvas coordinates on high-DPI displays.
        x_scale = max(float(logical_width), 1.0) / max(float(width), 1.0)
        y_scale = max(float(logical_height), 1.0) / max(float(height), 1.0)
        self.text_visual.pos = (
            SCALE_BAR_MARGIN_PIXELS * x_scale,
            max(float(logical_height) - SCALE_BAR_TEXT_BOTTOM_PIXELS * y_scale, 0.0),
            0.0,
        )

    def draw(self, *, canvas: object, camera: Camera) -> None:
        if camera.projection != "orthographic":
            return
        self.gloo.set_state(
            blend=True,
            depth_test=False,
            depth_mask=False,
            polygon_offset_fill=False,
            line_width=2.0,
        )
        self.overlay_program["a_position"] = self.positions
        self.overlay_program["u_color"] = self.overlay.color
        self.overlay_program.draw("lines")
        self.text_visual.transforms.configure(canvas=canvas)
        self.text_visual.draw()


def create_scale_bar_renderer(
    prepared: RenderScene,
    *,
    overlay_program: Any,
    visuals: Any,
    viewport_size: tuple[int, int],
    gloo: Any,
) -> ScaleBarRenderer | None:
    overlay = scale_bar_overlay(prepared)
    if overlay is None:
        return None
    return ScaleBarRenderer.create(
        overlay,
        overlay_program=overlay_program,
        visuals=visuals,
        viewport_size=viewport_size,
        gloo=gloo,
    )


def create_local_axes_renderer(
    prepared: RenderScene,
    *,
    local_centre: np.ndarray,
    gloo: Any,
) -> LocalAxesRenderer | None:
    overlay = local_axes_overlay(prepared)
    if overlay is None:
        return None
    return LocalAxesRenderer.create(
        overlay,
        local_centre=local_centre,
        gloo=gloo,
    )


__all__ = [
    "LocalAxesRenderer",
    "ScaleBar",
    "ScaleBarRenderer",
    "create_local_axes_renderer",
    "create_scale_bar_renderer",
    "local_axes_overlay",
    "scale_bar_for_camera",
    "scale_bar_for_visible_height",
    "scale_bar_overlay",
]
