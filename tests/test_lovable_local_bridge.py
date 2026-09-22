"""Static Lovable build delivery is strictly local and does not affect API routes."""
from __future__ import annotations

from pathlib import Path

import pytest

from chimera.product import STATIC, _static_asset, _static_root


def test_default_web_client_unchanged(monkeypatch):
    monkeypatch.delenv("CHIMERA_WEB_DIST", raising=False)
    assert _static_root() == STATIC


def test_compiled_frontend_is_opt_in(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setenv("CHIMERA_WEB_DIST", str(dist))
    with pytest.raises(ValueError, match="index.html"):
        _static_root()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    assert _static_root() == dist.resolve()


def test_only_shell_and_compiled_assets_are_readable(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("shell", encoding="utf-8")
    (assets / "index-123.js").write_text("export {}", encoding="utf-8")
    (dist / "secret.txt").write_text("do not serve", encoding="utf-8")
    assert _static_asset(dist, "/")[0] == dist / "index.html"
    assert _static_asset(dist, "/index.html")[0] == dist / "index.html"
    assert _static_asset(dist, "/assets/index-123.js")[0] == assets / "index-123.js"
    for path in (
        "/secret.txt", "/src/lib/chimera-api.ts", "/assets/../secret.txt",
        "/assets/%2e%2e/secret.txt", "/assets/%5c..%5csecret.txt",
        "/assets/.env", "/assets/missing.js",
    ):
        assert _static_asset(dist, path) is None, path


def test_asset_symlinks_do_not_escape_dist(tmp_path):
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    (assets / "outside.txt").symlink_to(outside)
    assert _static_asset(dist, "/assets/outside.txt") is None
