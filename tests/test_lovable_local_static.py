"""Local static UI integration: safe routing and MIME types without model calls."""
from pathlib import Path
from chimera.product import _static_asset, _static_root


def test_compiled_assets_are_served_without_directory_traversal(tmp_path: Path):
    (tmp_path / "index.html").write_text("<!doctype html>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-123.js").write_text("console.log(1)")
    (assets / "styles-123.css").write_text("body{}")
    (tmp_path / "favicon.ico").write_bytes(b"icon")
    (tmp_path / "robots.txt").write_text("User-agent: *")
    assert _static_asset(tmp_path, "/")[0] == tmp_path / "index.html"
    assert _static_asset(tmp_path, "/assets/index-123.js")[1].startswith("text/javascript")
    assert _static_asset(tmp_path, "/assets/styles-123.css")[1].startswith("text/css")
    assert _static_asset(tmp_path, "/favicon.ico")[0] == tmp_path / "favicon.ico"
    assert _static_asset(tmp_path, "/robots.txt")[0] == tmp_path / "robots.txt"
    for path in ("/assets/../index.html", "/assets/%2e%2e/index.html",
                 "/assets/.secret", "/assets/%5cindex-123.js",
                 "/api/features", "/private.txt"):
        assert _static_asset(tmp_path, path) is None


def test_missing_build_fails_closed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CHIMERA_WEB_DIST", str(tmp_path))
    import pytest
    with pytest.raises(ValueError, match="index.html"):
        _static_root()
    (tmp_path / "index.html").write_text("<!doctype html>")
    assert _static_root() == tmp_path.resolve()
