def test_smoke_import() -> None:
    import cady
    from cady import DxfDrawing, StlMesh, arc, circle, line, prism, sphere

    assert cady is not None
    assert all((line, arc, circle, sphere, prism, DxfDrawing, StlMesh))
