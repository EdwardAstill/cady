"""Convenience wrapper for flattening product assemblies."""

from __future__ import annotations

from cady.product.assembly import Assembly, FlattenedPart


def flatten_assembly(assembly: Assembly) -> tuple[FlattenedPart, ...]:
    """Return the recursively flattened part instances for an assembly."""
    return assembly.flatten()


__all__ = ["flatten_assembly"]
