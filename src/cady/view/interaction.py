"""Camera interaction state for the VisPy viewer backend."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, tan

import numpy as np

from cady.view.camera import Camera

ISOMETRIC_PITCH_DEGREES = 35.26438968
ISOMETRIC_VIEW_ANGLES: dict[str, tuple[float, float]] = {
    "6": (45.0, ISOMETRIC_PITCH_DEGREES),
    "7": (-45.0, ISOMETRIC_PITCH_DEGREES),
    "8": (-135.0, ISOMETRIC_PITCH_DEGREES),
    "9": (135.0, ISOMETRIC_PITCH_DEGREES),
}
LOCAL_AXIS_TURN_KEYS: dict[str, tuple[float, float, float]] = {
    "1": (1.0, 0.0, 0.0),
    "2": (0.0, 1.0, 0.0),
    "3": (0.0, 0.0, 1.0),
}
LOCAL_AXIS_VIEW_FRACTION = 0.22
ORTHOGRAPHIC_ZOOM_FACTOR = 0.9


def translation_matrix(offset: tuple[float, float, float] | np.ndarray) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float32)
    matrix[3, :3] = np.asarray(offset, dtype=np.float32)
    return matrix


def rotation_matrix(angle_degrees: float, axis: tuple[float, float, float]) -> np.ndarray:
    axis_array = np.asarray(axis, dtype=np.float32)
    length = float(np.linalg.norm(axis_array))
    if length == 0.0:
        raise ValueError("rotation axis must be non-zero")
    x, y, z = axis_array / length
    c = cos(radians(angle_degrees))
    s = np.sin(radians(angle_degrees))
    one_c = 1.0 - c
    return np.array(
        [
            [c + x * x * one_c, y * x * one_c + z * s, z * x * one_c - y * s, 0.0],
            [x * y * one_c - z * s, c + y * y * one_c, z * y * one_c + x * s, 0.0],
            [x * z * one_c + y * s, y * z * one_c - x * s, c + z * z * one_c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def apply_view_orbit(orientation: np.ndarray, dx_degrees: float, dy_degrees: float) -> np.ndarray:
    yaw = rotation_matrix(dx_degrees, (0.0, 1.0, 0.0))
    pitch = rotation_matrix(dy_degrees, (1.0, 0.0, 0.0))
    return (orientation @ yaw @ pitch).astype(np.float32, copy=False)


def front_orientation() -> np.ndarray:
    return np.eye(4, dtype=np.float32)


def camera_orientation(camera: Camera) -> np.ndarray:
    position = np.array(camera.position, dtype=np.float32)
    target = np.array(camera.target, dtype=np.float32)
    up_hint = np.array(camera.up, dtype=np.float32)
    z_axis = position - target
    z_axis = z_axis / np.linalg.norm(z_axis)
    x_axis = np.cross(up_hint, z_axis)
    x_axis = x_axis / np.linalg.norm(x_axis)
    y_axis = np.cross(z_axis, x_axis)
    matrix = np.eye(4, dtype=np.float32)
    matrix[:3, 0] = x_axis
    matrix[:3, 1] = y_axis
    matrix[:3, 2] = z_axis
    return matrix


def isometric_orientation(key: str) -> np.ndarray | None:
    angles = ISOMETRIC_VIEW_ANGLES.get(key)
    if angles is None:
        return None
    yaw_degrees, pitch_degrees = angles
    return apply_view_orbit(front_orientation(), yaw_degrees, pitch_degrees)


def apply_local_axis_turn(
    orientation: np.ndarray,
    axis: tuple[float, float, float],
) -> np.ndarray:
    return (rotation_matrix(90.0, axis) @ orientation).astype(np.float32, copy=False)


def orientation_for_number_key(orientation: np.ndarray, key: str) -> np.ndarray | None:
    if key == "0":
        return front_orientation()
    local_axis = LOCAL_AXIS_TURN_KEYS.get(key)
    if local_axis is not None:
        return apply_local_axis_turn(orientation, local_axis)
    return isometric_orientation(key)


def number_key_name(key: object) -> str | None:
    raw_name = getattr(key, "name", key)
    name = str(raw_name).lower()
    for digit in "0123456789":
        if name in {digit, f"digit{digit}", f"key{digit}", f"num{digit}", f"numpad{digit}"}:
            return digit
    return None


def axis_toggle_key_pressed(key: object) -> bool:
    raw_name = getattr(key, "name", key)
    return str(raw_name).lower() in {"a", "keya"}


def model_matrix(local_centre: np.ndarray, orientation: np.ndarray) -> np.ndarray:
    return (translation_matrix(-local_centre) @ orientation).astype(np.float32, copy=False)


def projection_clip_planes(radius: float, distance: float, camera: Camera) -> tuple[float, float]:
    near = max(camera.near, radius * 0.001, 0.01)
    far = max(camera.far if camera.far > near else near * 2.0, distance + radius * 4.0)
    return near, far


def view_relative_axis_length(
    distance: float,
    viewport_size: tuple[int, int],
    *,
    fov_degrees: float,
    view_fraction: float = LOCAL_AXIS_VIEW_FRACTION,
) -> float:
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    target_pixels = min(width_px, height_px) * view_fraction
    visible_world_height = 2.0 * max(float(distance), 1e-6) * tan(radians(fov_degrees) / 2.0)
    return target_pixels * visible_world_height / height_px


def view_relative_orthographic_axis_length(
    orthographic_scale: float,
    viewport_size: tuple[int, int],
    *,
    view_fraction: float = LOCAL_AXIS_VIEW_FRACTION,
) -> float:
    width, height = viewport_size
    width_px = max(float(width), 1.0)
    height_px = max(float(height), 1.0)
    target_pixels = min(width_px, height_px) * view_fraction
    return target_pixels * max(float(orthographic_scale), 1e-6) / height_px


def zoomed_orthographic_scale(
    scale: float,
    wheel_delta: float,
    radius: float,
) -> float:
    minimum = max(radius * 0.001, 1e-6)
    maximum = max(radius * 20.0, minimum * 2.0)
    zoomed = scale * (ORTHOGRAPHIC_ZOOM_FACTOR**wheel_delta)
    return max(minimum, min(float(zoomed), maximum))


@dataclass(slots=True)
class ViewerInteractionState:
    camera: Camera
    local_centre: np.ndarray
    radius: float
    distance: float
    pan: np.ndarray
    orientation: np.ndarray
    orthographic_scale: float

    @classmethod
    def from_camera(
        cls,
        camera: Camera,
        *,
        local_centre: np.ndarray,
        radius: float,
    ) -> ViewerInteractionState:
        requested_distance = float(
            np.linalg.norm(
                np.array(camera.position, dtype=np.float32)
                - np.array(camera.target, dtype=np.float32)
            )
        )
        return cls(
            camera=camera,
            local_centre=local_centre,
            radius=radius,
            distance=max(requested_distance, radius * 0.8),
            pan=np.zeros(2, dtype=np.float32),
            orientation=camera_orientation(camera),
            orthographic_scale=camera.orthographic_scale,
        )

    def view_matrix(self) -> np.ndarray:
        return translation_matrix((self.pan[0], self.pan[1], -self.distance))

    def model_matrix(self) -> np.ndarray:
        return model_matrix(self.local_centre, self.orientation)

    def local_axis_length(self, viewport_size: tuple[int, int]) -> float:
        if self.camera.projection == "orthographic":
            return view_relative_orthographic_axis_length(
                self.orthographic_scale,
                viewport_size,
            )
        return view_relative_axis_length(
            self.distance,
            viewport_size,
            fov_degrees=self.camera.fov_degrees,
        )

    def orbit(self, dx_pixels: float, dy_pixels: float) -> None:
        self.orientation = apply_view_orbit(
            self.orientation,
            dx_pixels * 0.5,
            dy_pixels * 0.5,
        )

    def pan_by_pixels(self, dx_pixels: float, dy_pixels: float) -> None:
        self.pan[0] += dx_pixels * self.radius * 0.003
        self.pan[1] -= dy_pixels * self.radius * 0.003

    def zoom(self, wheel_delta: float) -> None:
        if self.camera.projection == "orthographic":
            self.orthographic_scale = zoomed_orthographic_scale(
                self.orthographic_scale,
                wheel_delta,
                self.radius,
            )
            return
        self.distance -= wheel_delta * self.radius * 0.1
        self.distance = max(self.radius * 0.5, min(self.distance, self.radius * 20.0))

    def set_orientation_for_key(self, key: str) -> bool:
        orientation = orientation_for_number_key(self.orientation, key)
        if orientation is None:
            return False
        self.orientation = orientation
        return True


__all__ = [
    "ViewerInteractionState",
    "axis_toggle_key_pressed",
    "camera_orientation",
    "number_key_name",
    "projection_clip_planes",
    "view_relative_orthographic_axis_length",
    "zoomed_orthographic_scale",
]
