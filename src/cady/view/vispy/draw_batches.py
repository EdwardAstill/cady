"""Draw batch construction for the VisPy viewer backend."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from cady.view.scene import RenderScene, SceneLine, SceneMesh
from cady.view.vispy.mesh_buffers import orientation_edges, shaded_face_buffers

DEFAULT_EDGE_COLOR = (0.08, 0.12, 0.16)


@dataclass(frozen=True, slots=True)
class DrawBatch:
    positions: np.ndarray
    normals: np.ndarray
    colors: np.ndarray
    primitive: str
    index_buffer: object | None = None
    point_size: float = 4.0


@dataclass(frozen=True, slots=True)
class SceneBounds:
    local_centre: np.ndarray
    radius: float


@dataclass(frozen=True, slots=True)
class CanvasGeometry:
    face_batches: tuple[DrawBatch, ...]
    edge_batches: tuple[DrawBatch, ...]
    point_batches: tuple[DrawBatch, ...]
    bounds: SceneBounds


def mesh_edge_color(mesh: SceneMesh) -> tuple[float, float, float]:
    if mesh.render_mode == "wireframe":
        return mesh.color
    return DEFAULT_EDGE_COLOR


def vertex_attributes(
    positions: np.ndarray,
    normals: np.ndarray,
    colors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.ascontiguousarray(positions, dtype=np.float32),
        np.ascontiguousarray(normals, dtype=np.float32),
        np.ascontiguousarray(colors, dtype=np.float32),
    )


def solid_color_vertices(
    vertices: np.ndarray,
    color: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    colors = np.tile(np.array(color, dtype=np.float32), (len(vertices), 1))
    normals = np.tile(np.array((0.0, 0.0, 1.0), dtype=np.float32), (len(vertices), 1))
    return vertex_attributes(vertices, normals, colors)


def line_batch(line: SceneLine, gloo: Any) -> DrawBatch:
    positions, normals, colors = solid_color_vertices(line.vertices, line.color)
    return DrawBatch(
        positions=positions,
        normals=normals,
        colors=colors,
        primitive="lines",
        index_buffer=gloo.IndexBuffer(line.indices),
    )


def face_batch(mesh: SceneMesh, gloo: Any) -> DrawBatch | None:
    if mesh.render_mode != "shaded" or len(mesh.faces) == 0:
        return None
    face_vertices, face_indices, face_normals = shaded_face_buffers(
        mesh.vertices,
        mesh.faces,
    )
    colors = np.tile(np.array(mesh.color, dtype=np.float32), (len(face_vertices), 1))
    positions, normals, color_data = vertex_attributes(face_vertices, face_normals, colors)
    return DrawBatch(
        positions=positions,
        normals=normals,
        colors=color_data,
        primitive="triangles",
        index_buffer=gloo.IndexBuffer(face_indices),
    )


def edge_batch(mesh: SceneMesh, gloo: Any) -> DrawBatch | None:
    if mesh.render_mode not in {"shaded", "wireframe"}:
        return None
    # Semantic display edges take precedence; otherwise derive only visible
    # orientation edges so triangulation diagonals do not dominate the view.
    edge_indices = (
        mesh.edges
        if len(mesh.edges) > 0
        else orientation_edges(mesh.vertices, mesh.faces)
    )
    if len(edge_indices) == 0:
        return None
    positions, normals, colors = solid_color_vertices(mesh.vertices, mesh_edge_color(mesh))
    return DrawBatch(
        positions=positions,
        normals=normals,
        colors=colors,
        primitive="lines",
        index_buffer=gloo.IndexBuffer(edge_indices),
    )


def point_batch(mesh: SceneMesh) -> DrawBatch | None:
    if mesh.render_mode != "points":
        return None
    positions, normals, colors = solid_color_vertices(mesh.vertices, mesh.color)
    return DrawBatch(
        positions=positions,
        normals=normals,
        colors=colors,
        primitive="points",
        point_size=mesh.point_size,
    )


def scene_bounds(geometry_vertices: Sequence[np.ndarray]) -> SceneBounds:
    if not geometry_vertices:
        raise ValueError("viewer requires at least one vertex")
    all_vertices = np.vstack(geometry_vertices)
    local_centre = (all_vertices.min(axis=0) + all_vertices.max(axis=0)) / 2.0
    spans = all_vertices.max(axis=0) - all_vertices.min(axis=0)
    # The viewer orbits around the local centre; padding the largest span gives
    # short and flat geometry enough radius for clipping and overlay sizing.
    radius = float(np.max(spans)) * 1.2 or 1.0
    return SceneBounds(local_centre=local_centre, radius=radius)


def build_canvas_geometry(prepared: RenderScene, gloo: Any) -> CanvasGeometry:
    """Convert prepared scene arrays into GPU-ready draw batches."""
    face_batches: list[DrawBatch] = []
    edge_batches: list[DrawBatch] = []
    point_batches: list[DrawBatch] = []
    geometry_vertices: list[np.ndarray] = []

    for line in prepared.lines:
        geometry_vertices.append(line.vertices)
        edge_batches.append(line_batch(line, gloo))

    for mesh in prepared.meshes:
        geometry_vertices.append(mesh.vertices)
        face = face_batch(mesh, gloo)
        if face is not None:
            face_batches.append(face)
        edge = edge_batch(mesh, gloo)
        if edge is not None:
            edge_batches.append(edge)
        points = point_batch(mesh)
        if points is not None:
            point_batches.append(points)

    return CanvasGeometry(
        face_batches=tuple(face_batches),
        edge_batches=tuple(edge_batches),
        point_batches=tuple(point_batches),
        bounds=scene_bounds(geometry_vertices),
    )


__all__ = [
    "CanvasGeometry",
    "DrawBatch",
    "SceneBounds",
    "build_canvas_geometry",
    "mesh_edge_color",
    "solid_color_vertices",
]
