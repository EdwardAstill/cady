"""Shared helpers for file exporters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cady.errors import WriteError
from cady.utils import positive_tolerance

if TYPE_CHECKING:
    from cady.geometry import Mesh3


def mesh_from_target(target: object, *, tolerance: float) -> Mesh3:
    """Convert file-export targets to ``Mesh3``."""
    from cady.document import Document
    from cady.geometry import Mesh3

    try:
        positive_tolerance(tolerance)
    except ValueError as exc:
        raise WriteError(str(exc)) from exc

    if isinstance(target, Mesh3):
        return target

    if isinstance(target, Document):
        meshes = [
            mesh_from_target(item.value, tolerance=tolerance)
            for item in (*target.parts, *target.assemblies)
        ]
        if not meshes:
            raise WriteError("document contains no meshable parts or assemblies")
        return Mesh3.merged(meshes)

    to_mesh = getattr(target, "to_mesh", None)
    if callable(to_mesh):
        mesh = to_mesh(tolerance=tolerance)
        if isinstance(mesh, Mesh3):
            return mesh
        raise WriteError("to_mesh() must return Mesh3")

    raise WriteError(f"{type(target).__name__} is not meshable")


__all__ = ["mesh_from_target"]
