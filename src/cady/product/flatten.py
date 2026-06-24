from __future__ import annotations

from cady.product.assembly import Assembly, FlattenedPart


def flatten_assembly(assembly: Assembly) -> tuple[FlattenedPart, ...]:
    return assembly.flatten()


__all__ = ["flatten_assembly"]
