from pathlib import Path

from cady.files import step

STEP_FILE = Path(__file__).resolve().parents[2] / "files/padeye.step"
TOLERANCE = 1e-3


def view_step() -> None:
    step.read_mesh(STEP_FILE).view(title=f"STEP: {STEP_FILE.name}", tolerance=TOLERANCE)


if __name__ == "__main__":
    view_step()
