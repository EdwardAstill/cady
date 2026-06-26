from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Protocol

from cady.geometry.frame3d import Frame3D
from cady.utils import finite, positive

PrimitiveKind = Literal["box", "cylinder", "sphere", "cone"]
BooleanKind = Literal["union", "difference", "intersection"]


class Feature(Protocol):
    pass


@dataclass(frozen=True, slots=True)
class ProfileFeature:
    profile: object
    frame: Frame3D


@dataclass(frozen=True, slots=True)
class ExtrudeFeature:
    profile: object
    frame: Frame3D
    distance: float

    def __post_init__(self) -> None:
        distance = finite(self.distance, "extrude distance")
        if distance == 0.0:
            raise ValueError("extrude distance must be finite and non-zero")
        object.__setattr__(self, "distance", distance)


@dataclass(frozen=True, slots=True)
class RevolveFeature:
    profile: object
    frame: Frame3D
    angle: float

    def __post_init__(self) -> None:
        angle = finite(self.angle, "revolve angle")
        if angle == 0.0:
            raise ValueError("revolve angle must be finite and non-zero")
        object.__setattr__(self, "angle", angle)


@dataclass(frozen=True, slots=True)
class PrimitiveFeature:
    kind: PrimitiveKind
    parameters: Mapping[str, float]
    frame: Frame3D

    def __post_init__(self) -> None:
        if self.kind not in {"box", "cylinder", "sphere", "cone"}:
            raise ValueError(f"unsupported primitive kind {self.kind!r}")
        parameters = {key: finite(value, key) for key, value in self.parameters.items()}
        object.__setattr__(self, "parameters", MappingProxyType(parameters))


@dataclass(frozen=True, slots=True)
class BooleanFeature:
    kind: BooleanKind
    tool: object

    def __post_init__(self) -> None:
        if self.kind not in {"union", "difference", "intersection"}:
            raise ValueError(f"unsupported boolean kind {self.kind!r}")


@dataclass(frozen=True, slots=True)
class FilletFeature:
    radius: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "radius", positive(self.radius, "radius"))


@dataclass(frozen=True, slots=True)
class ChamferFeature:
    distance: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "distance", positive(self.distance, "distance"))
