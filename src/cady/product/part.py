from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cady.product.errors import ProductError
from cady.product.material import Material, Metadata, metadata_items

if TYPE_CHECKING:
    from cady.geometry import Mesh3D
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


def _mesh_from_target(target: object, *, tolerance: float) -> Mesh3D:
    from cady.geometry import Mesh3D

    if isinstance(target, Mesh3D):
        return target
    to_mesh = getattr(target, "to_mesh", None)
    if callable(to_mesh):
        mesh = to_mesh(tolerance=tolerance)
        if isinstance(mesh, Mesh3D):
            return mesh
        raise ProductError("to_mesh() must return Mesh3D")
    raise ProductError("part body is not meshable")


@dataclass(frozen=True, slots=True)
class Part:
    name: str
    bodies: tuple[object, ...] = field(default_factory=tuple)
    material: Material | None = None
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ProductError("part name cannot be empty")
        object.__setattr__(self, "bodies", tuple(self.bodies))
        object.__setattr__(self, "metadata", metadata_items(self.metadata))

    def with_body(self, body: object) -> Part:
        _validate_meshable_body(body)
        return Part(
            self.name,
            bodies=(*self.bodies, body),
            material=self.material,
            metadata=self.metadata,
        )

    def add_body(self, body: object) -> Part:
        return self.with_body(body)

    def with_bodies(self, *bodies: object) -> Part:
        part = self
        for body in bodies:
            part = part.with_body(body)
        return part

    def with_material(self, material: object | None) -> Part:
        if material is not None and not isinstance(material, Material):
            raise ProductError("material must be a Material")
        return Part(self.name, bodies=self.bodies, material=material, metadata=self.metadata)

    def with_metadata(self, **metadata: Any) -> Part:
        return Part(
            self.name,
            bodies=self.bodies,
            material=self.material,
            metadata=metadata_items(dict(self.metadata) | metadata),
        )

    def to_mesh(self, *, tolerance: float) -> Mesh3D:
        from cady.geometry import Mesh3D

        if tolerance <= 0.0:
            raise ProductError("tolerance must be positive")
        meshes = [_mesh_from_target(body, tolerance=tolerance) for body in self.bodies]
        return Mesh3D.merged(meshes)

    def view(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        camera: Camera | None = None,
        style: DisplayStyle | None = None,
        light: Light | None = None,
        color: tuple[float, float, float] | None = None,
        render_mode: RenderMode | None = None,
        projection: Projection = "orthographic",
        center: bool = True,
        tolerance: float = 1e-3,
    ) -> None:
        from cady.view.open_view import open_target_view

        open_target_view(
            self,
            name=name,
            title=title,
            camera=camera,
            style=style,
            light=light,
            color=color,
            render_mode=render_mode,
            projection=projection,
            center=center,
            tolerance=tolerance,
        )


def _validate_meshable_body(body: object) -> None:
    from cady.geometry import Mesh3D

    if isinstance(body, Mesh3D):
        return
    if callable(getattr(body, "to_mesh", None)):
        return
    raise ProductError("part bodies must be Mesh3D values or expose to_mesh(tolerance=...)")


def part_from_mapping(name: str, values: Mapping[str, object]) -> Part:
    part = Part(name)
    material = values.get("material")
    if material is not None:
        if not isinstance(material, Material):
            raise ProductError("material must be a Material")
        part = part.with_material(material)
    return part


__all__ = ["Part", "part_from_mapping"]
