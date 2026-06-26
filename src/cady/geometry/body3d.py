from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

from cady.geometry._mesh_builders import (
    box_mesh,
    cylinder_mesh,
    extrusion_mesh,
    sphere_mesh,
)
from cady.geometry.features import (
    BooleanFeature,
    ChamferFeature,
    ExtrudeFeature,
    Feature,
    FilletFeature,
    PrimitiveFeature,
    ProfileFeature,
    RevolveFeature,
)
from cady.geometry.frame3d import Frame3D, Point3Like
from cady.geometry.mesh3d import Mesh3D
from cady.operations.transforms import Transform3
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


@dataclass(frozen=True, slots=True)
class Body3D:
    name: str | None = None
    features: tuple[Feature, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", tuple(self.features))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_profile(
        cls,
        profile: object,
        *,
        frame: Frame3D | None = None,
    ) -> Body3D:
        return cls(features=(ProfileFeature(profile, frame or Frame3D.world_xy()),))

    @classmethod
    def box(
        cls,
        *,
        width: float,
        depth: float,
        height: float,
        frame: Frame3D | None = None,
    ) -> Body3D:
        return cls(
            features=(
                PrimitiveFeature(
                    "box",
                    {"width": width, "depth": depth, "height": height},
                    frame or Frame3D.world_xy(),
                ),
            )
        )

    @classmethod
    def cylinder(
        cls,
        *,
        radius: float,
        height: float,
        frame: Frame3D | None = None,
    ) -> Body3D:
        return cls(
            features=(
                PrimitiveFeature(
                    "cylinder",
                    {"radius": radius, "height": height},
                    frame or Frame3D.world_xy(),
                ),
            )
        )

    @classmethod
    def sphere(
        cls,
        *,
        radius: float,
        centre: Point3Like = (0.0, 0.0, 0.0),
    ) -> Body3D:
        return cls(
            features=(
                PrimitiveFeature(
                    "sphere",
                    {"radius": radius},
                    Frame3D.from_normal(promote3(centre), Vec3(0.0, 0.0, 1.0)),
                ),
            )
        )

    def extrude(
        self,
        distance: float,
        *,
        profile: object | None = None,
        frame: Frame3D | None = None,
    ) -> Body3D:
        if profile is None:
            profile_feature = self._last_profile_feature()
            resolved_profile = profile_feature.profile
            resolved_frame = frame or profile_feature.frame
        else:
            resolved_profile = profile
            resolved_frame = frame or Frame3D.world_xy()
        features = tuple(
            feature for feature in self.features if not isinstance(feature, ProfileFeature)
        )
        return replace(
            self,
            features=(*features, ExtrudeFeature(resolved_profile, resolved_frame, distance)),
        )

    def with_feature(self, feature: Feature) -> Body3D:
        return replace(self, features=(*self.features, feature))

    def transformed(self, transform: Transform3) -> Body3D:
        return replace(
            self,
            features=tuple(_transform_feature(feature, transform) for feature in self.features),
        )

    def to_mesh(self, *, tolerance: float) -> Mesh3D:
        meshes: list[Mesh3D] = []
        for feature in self.features:
            if isinstance(feature, ProfileFeature):
                continue
            if isinstance(feature, PrimitiveFeature):
                meshes.append(_primitive_to_mesh(feature, tolerance=tolerance))
                continue
            if isinstance(feature, ExtrudeFeature):
                meshes.append(
                    extrusion_mesh(
                        feature.profile,
                        feature.frame,
                        distance=feature.distance,
                        tolerance=tolerance,
                    )
                )
                continue
            if isinstance(feature, RevolveFeature):
                raise NotImplementedError("revolve feature evaluation is not implemented")
            if isinstance(feature, BooleanFeature):
                raise NotImplementedError("boolean feature evaluation is not implemented")
            if isinstance(feature, FilletFeature | ChamferFeature):
                raise NotImplementedError(
                    "fillet and chamfer feature evaluation is not implemented"
                )
            raise TypeError(f"unsupported feature {type(feature).__name__}")
        if not meshes:
            raise ValueError("body has no meshable features")
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

    def _last_profile_feature(self) -> ProfileFeature:
        for feature in reversed(self.features):
            if isinstance(feature, ProfileFeature):
                return feature
        raise ValueError("profile is required when body has no stored profile")


def _primitive_to_mesh(feature: PrimitiveFeature, *, tolerance: float) -> Mesh3D:
    parameters = feature.parameters
    if feature.kind == "box":
        return box_mesh(
            feature.frame,
            width=parameters["width"],
            depth=parameters["depth"],
            height=parameters["height"],
        )
    if feature.kind == "cylinder":
        return cylinder_mesh(
            feature.frame,
            radius=parameters["radius"],
            height=parameters["height"],
            tolerance=tolerance,
        )
    if feature.kind == "sphere":
        return sphere_mesh(feature.frame, radius=parameters["radius"], tolerance=tolerance)
    raise NotImplementedError(f"{feature.kind} primitive evaluation is not implemented")


def _transform_feature(feature: Feature, transform: Transform3) -> Feature:
    if isinstance(feature, ProfileFeature):
        return replace(feature, frame=feature.frame.transformed(transform))
    if isinstance(feature, ExtrudeFeature):
        return replace(feature, frame=feature.frame.transformed(transform))
    if isinstance(feature, PrimitiveFeature):
        return replace(feature, frame=feature.frame.transformed(transform))
    if isinstance(feature, RevolveFeature):
        return replace(feature, frame=feature.frame.transformed(transform))
    return feature
