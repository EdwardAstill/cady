def test_smoke_import() -> None:
    import cad
    from cad import DxfDrawing, StlMesh, arc, circle, line, prism, sphere

    assert cad is not None
    assert all((line, arc, circle, sphere, prism, DxfDrawing, StlMesh))
