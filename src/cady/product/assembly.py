from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cady.product.errors import ProductError
from cady.product.material import Metadata, metadata_items
from cady.product.part import Part

if TYPE_CHECKING:
    from cady.numeric.mesh3d import ArrayMesh3
    from cady.numeric.transform import Transform3
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


def _transform_from_pose(pose: object | None) -> Transform3:
    from cady.numeric.transform import Transform3

    if pose is None:
        return Transform3.identity()
    if isinstance(pose, Transform3):
        return pose
    to_transform3 = getattr(pose, "to_transform3", None)
    if callable(to_transform3):
        transform = to_transform3()
        if isinstance(transform, Transform3):
            return transform
    try:
        values = tuple(float(component) for component in pose)  # type: ignore[reportUnknownVariableType]
    except TypeError:
        values = ()
    if len(values) == 3:
        return Transform3.translation(values[0], values[1], values[2])
    raise ProductError("pose must be None, Transform3, Pose3-like, or a 3D translation")


def _compose(parent: Transform3, child: Transform3) -> Transform3:
    return parent.compose(child)


@dataclass(frozen=True, slots=True)
class PartInstance:
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
        return self.name or self.part.name


@dataclass(frozen=True, slots=True)
class AssemblyInstance:
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
        return self.name or self.assembly.name


@dataclass(frozen=True, slots=True)
class FlattenedPart:
    part: Part
    name: str
    transform: Transform3
    path: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Assembly:
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

    def add(
        self,
        target: Part | Assembly,
        *,
        name: str | None = None,
        pose: object | None = None,
    ) -> Assembly:
        if isinstance(target, Part):
            return self.add_part(target, name=name, pose=pose)
        return self.add_assembly(target, name=name, pose=pose)

    def add_part(
        self,
        part: Part,
        *,
        name: str | None = None,
        pose: object | None = None,
        metadata: Mapping[str, Any] | Metadata | None = None,
    ) -> Assembly:
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
        return Assembly(
            self.name,
            part_instances=self.part_instances,
            assembly_instances=self.assembly_instances,
            metadata=metadata_items(dict(self.metadata) | metadata),
        )

    def flatten(self) -> tuple[FlattenedPart, ...]:
        return _flatten_assembly(self, _transform_from_pose(None), (), set())

    def to_mesh(self, *, tolerance: float) -> ArrayMesh3:
        from cady.numeric.mesh3d import ArrayMesh3

        if tolerance <= 0.0:
            raise ProductError("tolerance must be positive")
        meshes: list[ArrayMesh3] = []
        for item in self.flatten():
            mesh = item.part.to_mesh(tolerance=tolerance)
            meshes.append(mesh.transformed(item.transform))
        return ArrayMesh3.merged(meshes)

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


def _flatten_assembly(
    assembly: Assembly,
    parent_transform: Transform3,
    parent_path: tuple[str, ...],
    seen: set[int],
) -> tuple[FlattenedPart, ...]:
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
    names = [instance.instance_name for instance in instances]
    if len(names) != len(set(names)):
        raise ProductError("duplicate instance names are not allowed in an assembly")


__all__ = [
    "Assembly",
    "AssemblyInstance",
    "FlattenedPart",
    "PartInstance",
]
