from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Literal, Protocol

from cady.geometry3d.frame import Frame3D

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
        distance = float(self.distance)
        if not isfinite(distance) or distance == 0.0:
            raise ValueError("extrude distance must be finite and non-zero")
        object.__setattr__(self, "distance", distance)


@dataclass(frozen=True, slots=True)
class RevolveFeature:
    profile: object
    frame: Frame3D
    angle: float

    def __post_init__(self) -> None:
        angle = float(self.angle)
        if not isfinite(angle) or angle == 0.0:
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
        parameters = {key: _finite(value, key) for key, value in self.parameters.items()}
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
        object.__setattr__(self, "radius", _positive(self.radius, "radius"))


@dataclass(frozen=True, slots=True)
class ChamferFeature:
    distance: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "distance", _positive(self.distance, "distance"))


def _finite(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _positive(value: float, name: str) -> float:
    value = _finite(value, name)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")
    return value
