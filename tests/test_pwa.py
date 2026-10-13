"""PWA checks: manifest/icons validity, worker serving + safety, loopback bind."""

import json
import struct
import tempfile
import urllib.request
from pathlib import Path

import pytest

from shellshelf import server as server_mod
from shellshelf.server import serve


def _client(port):
    base = f"http://127.0.0.1:{port}"

    def call(method, path, body=None):
        data = json.dumps(body or {}).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, res.headers.get("Content-Type", ""), res.read()
        except Exception as exc:  # HTTPError carries the status
            code = getattr(exc, "code", 500)
            ctype = exc.headers.get("Content-Type", "") if hasattr(exc, "headers") else ""
            try:
                return code, ctype, exc.read()
            except Exception:
                return code, ctype, b""
    return call


@pytest.fixture()
def server():
    with tempfile.TemporaryDirectory() as tmp:
        srv = serve(port=0, data_dir=Path(tmp))
        import threading
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        yield srv.server_address[1]
        srv.shutdown()


def _png_size(raw: bytes) -> tuple[int, int]:
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", raw[16:24])


def test_manifest_valid_and_icons_served(server):
    call = _client(server)
    status, ctype, raw = call("GET", "/static/manifest.webmanifest")
    assert status == 200, raw
    assert "application/manifest+json" in ctype
    manifest = json.loads(raw.decode("utf-8"))
    assert manifest["name"] == "ShellShelf"
    assert manifest["short_name"] == "ShellShelf"
    assert manifest["display"] == "standalone"
    assert manifest["theme_color"] and manifest["background_color"]
    assert manifest["start_url"] == "/" and manifest["scope"] == "/"
    assert len(manifest["icons"]) >= 2
    for icon in manifest["icons"]:
        status, ctype, body = call("GET", icon["src"])
        assert status == 200, icon["src"]
        if icon["type"] == "image/png":
            assert "image/png" in ctype
            assert _png_size(body) == tuple(int(x) for x in icon["sizes"].split("x"))
        elif icon["type"] == "image/svg+xml":
            assert "image/svg+xml" in ctype


def test_apple_touch_icon_served(server):
    call = _client(server)
    status, ctype, raw = call("GET", "/static/icons/apple-touch-icon.png")
    assert status == 200
    assert "image/png" in ctype
    assert _png_size(raw) == (180, 180)


def test_service_worker_served_and_caches_shell_only(server):
    call = _client(server)
    status, ctype, raw = call("GET", "/sw.js")
    assert status == 200
    assert "javascript" in ctype
    src = raw.decode("utf-8")
    # API and user data must stay network-only: an explicit bypass exists and
    # nothing is ever written to the cache at request time.
    assert '/api/' in src
    assert 'cache.put' not in src
    assert 'addAll(SHELL_ASSETS)' in src or 'addAll(SHELL' in src
    # Every precached path is an app-shell file, never API/data.
    import re
    listed = re.findall(r'"(/[a-zA-Z0-9/._-]*)"', src.split("SHELL_ASSETS")[1].split("];")[0])
    assert listed, "SHELL_ASSETS must list shell paths"
    assert all(not p.startswith("/api") for p in listed)


def test_backend_binds_loopback_only():
    with tempfile.TemporaryDirectory() as tmp:
        srv = serve(port=0, data_dir=Path(tmp))
        try:
            assert srv.server_address[0] == "127.0.0.1"
        finally:
            srv.server_close()
    for module_file in ("shellshelf/server.py", "app.py", "packaging/build.py"):
        assert "0.0.0.0" not in Path(module_file).read_text(encoding="utf-8")


def test_static_traversal_rejected_but_icon_subpaths_allowed(server):
    call = _client(server)
    status, _, _ = call("GET", "/static/../app.py")
    assert status == 400
    status, ctype, _ = call("GET", "/static/icons/icon-192.png")
    assert status == 200
    assert "image/png" in ctype
