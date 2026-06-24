from cady.errors import (
    CadError,
    DrawingError,
    GeometryError,
    ProductError,
    ReadError,
    ViewError,
    WriteError,
)


def test_error_tiers_share_cad_base() -> None:
    tiers = (
        GeometryError,
        DrawingError,
        ProductError,
        ViewError,
        ReadError,
        WriteError,
    )

    for tier in tiers:
        assert issubclass(tier, CadError)


def test_error_tiers_remain_exceptions() -> None:
    assert isinstance(GeometryError("bad geometry"), Exception)
    assert isinstance(DrawingError("bad drawing"), Exception)
    assert isinstance(ProductError("bad product"), Exception)
    assert isinstance(ViewError("bad view"), Exception)
    assert isinstance(ReadError("bad input"), Exception)
    assert isinstance(WriteError("bad output"), Exception)
