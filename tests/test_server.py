"""Integration tests for the HTTP API: CRUD, import preview, launch confirmation."""

import json
import tempfile
import urllib.request
from pathlib import Path

import pytest

from shellshelf.server import serve


def _client(port):
    base = f"http://127.0.0.1:{port}"

    def call(method, path, body=None):
        data = json.dumps(body or {}).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read().decode())
        except Exception as exc:  # HTTPError carries body
            raw = exc.read().decode() if hasattr(exc, "read") else ""
            try:
                return exc.code, json.loads(raw)
            except Exception:
                return getattr(exc, "code", 500), {"errors": [raw or str(exc)]}
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


def test_full_workflow_add_find_launch_explicitly(server):
    call = _client(server)
    status, data = call("POST", "/api/shortcuts", {"name": "Greet", "command": "echo hello"})
    assert status == 201, data
    sid = data["shortcut"]["id"]

    status, data = call("GET", "/api/shortcuts?q=greet")
    assert status == 200 and len(data["shortcuts"]) == 1

    # Launch without confirmation must fail (never auto-run).
    status, data = call("POST", "/api/launch", {"id": sid})
    assert status == 400

    status, data = call("POST", "/api/launch", {"id": sid, "confirmed": True})
    assert status == 200, data
    assert data["returncode"] == 0
    assert "hello" in data["stdout"]


def test_import_preview_before_save_and_no_rc_modification(server, tmp_path=None):
    import tempfile, os
    call = _client(server)
    with tempfile.NamedTemporaryFile("w", suffix=".bashrc", delete=False) as fh:
        fh.write("alias ll='ls -la'\nalias evil='echo $(whoami)'\n")
        path = fh.name
    before = open(path).read()
    status, data = call("POST", "/api/import/preview", {"path": path})
    assert status == 200
    assert [e["name"] for e in data["entries"]] == ["ll"]
    assert len(data["skipped"]) == 1
    assert open(path).read() == before  # import is read-only
    os.unlink(path)

    status, data = call("POST", "/api/import/confirm",
                        {"entries": [{"name": "ll", "command": "ls -la", "origin": "test"}]})
    assert status == 200 and len(data["imported"]) == 1


def test_static_served_from_disk_and_from_zip_fallback(monkeypatch, tmp_path):
    import sys as _sys
    import zipfile

    from shellshelf import server as server_mod

    assert server_mod.read_static_bytes("index.html").startswith(b"<!DOCTYPE html")
    assert server_mod.read_static_bytes("../app.py") is None

    # Simulate running from inside a zipapp: break the disk path and point
    # sys.argv[0] at a temp archive containing the static file.
    archive = tmp_path / "fake.pyz"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("static/index.html", b"<p>from zip</p>")
    monkeypatch.setattr(server_mod, "STATIC_DIR", tmp_path / "missing")
    monkeypatch.setattr(_sys, "argv", [str(archive)])
    assert server_mod.read_static_bytes("index.html") == b"<p>from zip</p>"
