from tests.conftest import run_pyright


def test_transform_arity_static_errors() -> None:
    result = run_pyright("tests/geom/transform_typing.py")
    assert result.returncode != 0
    assert (
        "Expected 2 positional arguments" in result.stdout
        or "Expected 3 positional arguments" in result.stdout
    )
    assert "with_hole" in result.stdout
