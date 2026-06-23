from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self

from cady.domain.drawing import DxfDrawing
from cady.domain.model import Drawing2D, Model
from cady.errors import WriteError
from cady.files.dxf import write_drawing as write_dxf_drawing
from cady.files.dxf import write_model as write_dxf_model

DWG_CONVERTER_ENV = "CADY_DWG_CONVERTER"


@dataclass(frozen=True, slots=True)
class DwgConverter:
    """Command-line DXF/DWG converter.

    Commands may include ``{input}`` and ``{output}`` placeholders. If neither
    placeholder is present, cady appends the input and output paths.
    """

    command: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.command:
            raise ValueError("DWG converter command cannot be empty")

    @classmethod
    def from_command(cls, command: str | Sequence[str]) -> Self:
        parts = tuple(shlex.split(command)) if isinstance(command, str) else tuple(command)
        return cls(parts)

    def command_line(self, input_path: Path, output_path: Path) -> list[str]:
        input_text = str(input_path)
        output_text = str(output_path)
        has_placeholders = any(
            "{input}" in part or "{output}" in part for part in self.command
        )
        command = [
            part.replace("{input}", input_text).replace("{output}", output_text)
            for part in self.command
        ]
        if not has_placeholders:
            command.extend([input_text, output_text])
        return command

    def convert(self, input_path: Path, output_path: Path) -> None:
        command = self.command_line(input_path, output_path)
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            raise WriteError(f"DWG converter could not be started: {command[0]}: {exc}") from exc

        if completed.returncode != 0:
            detail = _converter_output(completed)
            message = f"DWG converter failed with exit code {completed.returncode}"
            if detail:
                message = f"{message}: {detail}"
            raise WriteError(message)
        if not output_path.exists():
            raise WriteError(f"DWG converter did not create output file: {output_path}")


def converter_from_env() -> DwgConverter | None:
    command = os.environ.get(DWG_CONVERTER_ENV)
    if command is None:
        return None
    return DwgConverter.from_command(command)


def write_drawing(
    drawing: Drawing2D | DxfDrawing,
    path: str | Path,
    *,
    converter: DwgConverter | None = None,
) -> Drawing2D | DxfDrawing:
    output_path = Path(path)
    resolved_converter = _resolve_converter(converter)
    with TemporaryDirectory(prefix="cady-dwg-") as tmp_dir:
        dxf_path = Path(tmp_dir) / f"{output_path.stem or 'drawing'}.dxf"
        write_dxf_drawing(drawing, dxf_path)
        resolved_converter.convert(dxf_path, output_path)
    return drawing


def write_model(
    model: Model,
    path: str | Path,
    *,
    converter: DwgConverter | None = None,
) -> Model:
    output_path = Path(path)
    resolved_converter = _resolve_converter(converter)
    with TemporaryDirectory(prefix="cady-dwg-") as tmp_dir:
        dxf_path = Path(tmp_dir) / f"{output_path.stem or model.name or 'model'}.dxf"
        write_dxf_model(model, dxf_path)
        resolved_converter.convert(dxf_path, output_path)
    return model


def convert_to_dxf(
    path: str | Path,
    output_path: str | Path,
    *,
    converter: DwgConverter | None = None,
) -> Path:
    target_path = Path(output_path)
    _resolve_converter(converter).convert(Path(path), target_path)
    return target_path


def _resolve_converter(converter: DwgConverter | None) -> DwgConverter:
    if converter is not None:
        return converter
    try:
        env_converter = converter_from_env()
    except ValueError as exc:
        raise WriteError(f"{DWG_CONVERTER_ENV} must name a converter command") from exc
    if env_converter is not None:
        return env_converter
    raise WriteError(
        "DWG support requires an external converter. Pass converter=DwgConverter(...) "
        f"or set {DWG_CONVERTER_ENV}. cady writes DXF internally and does not "
        "natively serialize proprietary DWG bytes."
    )


def _converter_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part.strip()
    )


__all__ = [
    "DWG_CONVERTER_ENV",
    "DwgConverter",
    "convert_to_dxf",
    "converter_from_env",
    "write_drawing",
    "write_model",
]
