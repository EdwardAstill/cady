"""Assembly containers, instances, and flattening helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cady.product.errors import ProductError
from cady.product.material import Metadata, metadata_items
from cady.product.part import Part

if TYPE_CHECKING:
    from cady.geometry import Mesh3
    from cady.operations.transforms import Transform3
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.style import RenderMode
    from cady.view.viewer import Projection


def _transform_from_pose(pose: object | None) -> Transform3:
    """Coerce an optional pose-like value to a concrete transform."""
    from cady.operations.transforms import Transform3

    try:
        return Transform3.coerce(pose, allow_none=True)
    except TypeError as exc:
        raise ProductError(
            "pose must be None, Transform3-like, or a 3D translation"
        ) from exc


def _compose(parent: Transform3, child: Transform3) -> Transform3:
    return parent.compose(child)


@dataclass(frozen=True, slots=True)
class PartInstance:
    """Placed instance of a part within an assembly."""

    part: Part
    name: str | None = None
    pose: object | None = None
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.name is not None and not self.name:
            raise ProductError("part instance name cannot be empty")
        _transform_from_pose(self.pose)
        object.__setattr__(self, "metadata", metadata_items(self.metadata))

    @property
    def instance_name(self) -> str:
        """Return the explicit instance name or fall back to the part name."""
        return self.name or self.part.name


@dataclass(frozen=True, slots=True)
class AssemblyInstance:
    """Placed instance of a child assembly within a parent assembly."""

    assembly: Assembly
    name: str | None = None
    pose: object | None = None
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.name is not None and not self.name:
            raise ProductError("assembly instance name cannot be empty")
        _transform_from_pose(self.pose)
        object.__setattr__(self, "metadata", metadata_items(self.metadata))

    @property
    def instance_name(self) -> str:
        """Return the explicit instance name or fall back to the assembly name."""
        return self.name or self.assembly.name


@dataclass(frozen=True, slots=True)
class FlattenedPart:
    """Part instance resolved to world transform and traversal path."""

    part: Part
    name: str
    transform: Transform3
    path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Assembly:
    """Hierarchical collection of part and assembly instances."""

    name: str
    part_instances: tuple[PartInstance, ...] = field(default_factory=tuple)
    assembly_instances: tuple[AssemblyInstance, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ProductError("assembly name cannot be empty")
        object.__setattr__(self, "part_instances", tuple(self.part_instances))
        object.__setattr__(self, "assembly_instances", tuple(self.assembly_instances))
        object.__setattr__(self, "metadata", metadata_items(self.metadata))
        _reject_duplicate_instance_names((*self.part_instances, *self.assembly_instances))
        _detect_cycles(self)

    def add_part(
        self,
        part: Part,
        *,
        name: str | None = None,
        pose: object | None = None,
        metadata: Mapping[str, Any] | Metadata | None = None,
    ) -> Assembly:
        """Return a new assembly with an added part instance."""
        instance = PartInstance(part, name=name, pose=pose, metadata=metadata_items(metadata))
        return Assembly(
            self.name,
            part_instances=(*self.part_instances, instance),
            assembly_instances=self.assembly_instances,
            metadata=self.metadata,
        )

    def add_assembly(
        self,
        assembly: Assembly,
        *,
        name: str | None = None,
        pose: object | None = None,
        metadata: Mapping[str, Any] | Metadata | None = None,
    ) -> Assembly:
        """Return a new assembly with an added child assembly instance."""
        if assembly is self or _contains_assembly(assembly, self):
            raise ProductError("assembly cycle detected")
        instance = AssemblyInstance(
            assembly,
            name=name,
            pose=pose,
            metadata=metadata_items(metadata),
        )
        return Assembly(
            self.name,
            part_instances=self.part_instances,
            assembly_instances=(*self.assembly_instances, instance),
            metadata=self.metadata,
        )

    def with_metadata(self, **metadata: Any) -> Assembly:
        """Return a new assembly with merged metadata values."""
        return Assembly(
            self.name,
            part_instances=self.part_instances,
            assembly_instances=self.assembly_instances,
            metadata=metadata_items(dict(self.metadata) | metadata),
        )

    def flatten(self) -> tuple[FlattenedPart, ...]:
        """Resolve the assembly tree into positioned part instances."""
        return _flatten_assembly(self, _transform_from_pose(None), (), set())

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        """Mesh every flattened part and merge the transformed results."""
        from cady.geometry import Mesh3

        if tolerance <= 0.0:
            raise ProductError("tolerance must be positive")
        meshes: list[Mesh3] = []
        for item in self.flatten():
            mesh = item.part.to_mesh(tolerance=tolerance)
            meshes.append(mesh.transformed(item.transform))
        return Mesh3.merged(meshes)

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
        from cady.view.viewer import open_target_view

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


def _flatten_assembly(
    assembly: Assembly,
    parent_transform: Transform3,
    parent_path: tuple[str, ...],
    seen: set[int],
) -> tuple[FlattenedPart, ...]:
    """Walk the assembly tree and accumulate transforms and path names."""
    identity = id(assembly)
    if identity in seen:
        raise ProductError("assembly cycle detected")
    next_seen = {*seen, identity}
    path = (*parent_path, assembly.name)
    flattened: list[FlattenedPart] = []
    for instance in assembly.part_instances:
        transform = _compose(parent_transform, _transform_from_pose(instance.pose))
        flattened.append(
            FlattenedPart(
                instance.part,
                instance.instance_name,
                transform,
                (*path, instance.instance_name),
            )
        )
    for instance in assembly.assembly_instances:
        transform = _compose(parent_transform, _transform_from_pose(instance.pose))
        # Carry the composed transform and full traversal path into child assemblies.
        flattened.extend(
            _flatten_assembly(
                instance.assembly,
                transform,
                (*path, instance.instance_name),
                next_seen,
            )
        )
    return tuple(flattened)


def _contains_assembly(root: Assembly, target: Assembly, seen: set[int] | None = None) -> bool:
    """Return whether ``target`` already appears within ``root``."""
    seen = set() if seen is None else seen
    identity = id(root)
    if identity in seen:
        raise ProductError("assembly cycle detected")
    if root is target or root.name == target.name:
        return True
    seen.add(identity)
    return any(
        _contains_assembly(child.assembly, target, seen)
        for child in root.assembly_instances
    )


def _detect_cycles(assembly: Assembly, seen: set[int] | None = None) -> None:
    """Raise if an assembly graph contains a recursive reference."""
    seen = set() if seen is None else seen
    identity = id(assembly)
    if identity in seen:
        raise ProductError("assembly cycle detected")
    seen.add(identity)
    for instance in assembly.assembly_instances:
        _detect_cycles(instance.assembly, set(seen))


def _reject_duplicate_instance_names(
    instances: tuple[PartInstance | AssemblyInstance, ...],
) -> None:
    """Reject sibling instances that would collide by visible name."""
    names = [instance.instance_name for instance in instances]
    if len(names) != len(set(names)):
        raise ProductError("duplicate instance names are not allowed in an assembly")


__all__ = [
    "Assembly",
    "AssemblyInstance",
    "FlattenedPart",
    "PartInstance",
]
