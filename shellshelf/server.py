"""Local HTTP backend (stdlib only). Serves UI + JSON API. Never auto-launches."""

from __future__ import annotations

import json
import os
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .alias_parser import CANDIDATE_FILES, parse_alias_text, read_alias_file
from .launcher import build_launch_spec, get_platform, run_capture
from .model import Shortcut
from .storage import ShortcutStore

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def read_static_bytes(name: str) -> bytes | None:
    """Read a bundled frontend file, from disk or from inside a zipapp archive.

    `name` is relative to `static/` (e.g. `"app.js"`, `"icons/icon-192.png"`).
    Path traversal outside `static/` is rejected. Returns None when missing.
    Pure read-only helper.
    """
    if not name or ".." in name or name.startswith("/"):
        return None
    try:
        base = STATIC_DIR.resolve()
        target = (STATIC_DIR / name).resolve()
        if target != base and base not in target.parents:
            return None
        return target.read_bytes()
    except OSError:
        pass
    # Fallback: running from `dist/shellshelf.pyz` — `__file__` points inside
    # the archive, so plain path reads fail; read from the zip instead.
    try:
        archive = sys.argv[0]
        if archive.endswith((".pyz", ".zip")) and Path(archive).is_file():
            with zipfile.ZipFile(archive) as zf:
                return zf.read(f"static/{name}")
    except (OSError, KeyError, zipfile.BadZipFile):
        pass
    return None


STATIC_CONTENT_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".webmanifest": "application/manifest+json",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def static_content_type(name: str) -> str:
    return STATIC_CONTENT_TYPES.get(Path(name).suffix.lower(), "text/plain; charset=utf-8")


def _json(handler: BaseHTTPRequestHandler, status: int, payload: dict | list) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


class Handler(BaseHTTPRequestHandler):
    store: ShortcutStore = None  # set by serve()

    def log_message(self, fmt, *args):  # quieter logs
        pass

    # -- static ---------------------------------------------------------
    def _serve_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(404, "Not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, name: str, content_type: str) -> None:
        body = read_static_bytes(name)
        if body is None:
            self.send_error(404, "Not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            return self._serve_static("index.html", "text/html; charset=utf-8")
        if parsed.path == "/sw.js":
            # Served from the root so the worker's scope covers the whole app.
            return self._serve_static("sw.js", "text/javascript; charset=utf-8")
        if parsed.path.startswith("/static/"):
            name = unquote(parsed.path[len("/static/"):])
            if not name or ".." in name or name.startswith("/"):
                return self.send_error(400, "Bad path")
            return self._serve_static(name, static_content_type(name))
        if parsed.path == "/api/shortcuts":
            qs = parse_qs(parsed.query)
            q = (qs.get("q", [""])[0])
            fav = (qs.get("favorites", [""])[0]).lower() in ("1", "true", "yes")
            items = [s.to_dict() for s in self.store.list(query=q, favorites_only=fav)]
            return _json(self, 200, {"shortcuts": items})
        if parsed.path == "/api/import/candidates":
            out = []
            for raw, label in CANDIDATE_FILES:
                p = Path(os.path.expanduser(raw))
                out.append({"path": str(p), "label": label, "exists": p.exists()})
            return _json(self, 200, {"candidates": out, "platform": get_platform()})
        return self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/shortcuts":
            data = _read_json_body(self)
            sc, errors = self.store.add(data)
            if errors:
                return _json(self, 400, {"errors": errors})
            return _json(self, 201, {"shortcut": sc.to_dict()})
        if parsed.path == "/api/import/preview":
            data = _read_json_body(self)
            text = data.get("text", "")
            path = str(data.get("path", "")).strip()
            origin = "paste"
            if path:
                # Safety: read as text only; never source/execute. Restrict to
                # files the user explicitly names in this request.
                try:
                    text = read_alias_file(os.path.expanduser(path))
                    origin = path
                except OSError as exc:
                    return _json(self, 400, {"errors": [f"Could not read file: {exc}"]})
            entries, skipped = parse_alias_text(text or "", origin=origin)
            existing = {s.name.strip().lower() for s in self.store.list()}
            payload_entries = []
            for e in entries:
                payload_entries.append({
                    "name": e.name, "command": e.command, "line_no": e.line_no,
                    "duplicate": e.name.strip().lower() in existing,
                })
            return _json(self, 200, {
                "entries": payload_entries,
                "skipped": [{"line_no": s.line_no, "line": s.line, "reason": s.reason} for s in skipped],
            })
        if parsed.path == "/api/import/confirm":
            data = _read_json_body(self)
            items = data.get("entries", [])
            if not isinstance(items, list):
                return _json(self, 400, {"errors": ["'entries' must be a list."]})
            imported: list[dict] = []
            errors: list[str] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                payload = {
                    "name": str(item.get("name", "")),
                    "command": str(item.get("command", "")),
                    "launch_mode": str(item.get("launch_mode", "terminal")),
                    "source": f"import:{str(item.get('origin', 'file'))}"[:200],
                    "description": str(item.get("description", "")),
                }
                sc, errs = self.store.add(payload)
                if errs:
                    errors.append(f"{payload['name'] or '?'}: {'; '.join(errs)}")
                else:
                    imported.append(sc.to_dict())
            return _json(self, 200, {"imported": imported, "errors": errors})
        if parsed.path == "/api/launch":
            data = _read_json_body(self)
            shortcut_id = str(data.get("id", ""))
            confirmed = bool(data.get("confirmed", False))
            via_shell_ack = bool(data.get("via_shell_ack", False))
            dry_run = bool(data.get("dry_run", False))
            if not confirmed:
                return _json(self, 400, {
                    "errors": ["Launch requires explicit confirmation (confirmed=true). Imported commands never run automatically."],
                })
            sc: Shortcut | None = self.store.get(shortcut_id)
            if sc is None:
                return _json(self, 404, {"errors": ["Shortcut not found."]})
            try:
                spec = build_launch_spec(sc.command, sc.launch_mode)
            except ValueError as exc:
                return _json(self, 400, {"errors": [str(exc)]})
            if spec.needs_shell and not via_shell_ack:
                return _json(self, 409, {
                    "errors": ["This command needs a shell ('sh -c'). Tick the acknowledgement to run it."],
                    "spec": {"argv": spec.argv, "explanation": spec.explanation,
                             "display_command": spec.display_command, "needs_shell": True},
                })
            if dry_run or sc.launch_mode == "app":
                # For apps, do not auto-spawn from tests/dry runs; return argv.
                # Real UI launches apps via the same explicit endpoint without dry_run
                # on the user's own machine; headless CI stays safe.
                if dry_run:
                    return _json(self, 200, {"spec": {
                        "argv": spec.argv, "explanation": spec.explanation,
                        "display_command": spec.display_command,
                        "needs_shell": spec.needs_shell, "kind": spec.kind}})
            if sc.launch_mode == "app":
                import subprocess as _sp
                try:
                    _sp.Popen(spec.argv, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, shell=False)
                except OSError as exc:
                    return _json(self, 500, {"errors": [f"Failed to launch: {exc}"]})
                return _json(self, 200, {"ok": True, "spec": {
                    "argv": spec.argv, "explanation": spec.explanation,
                    "display_command": spec.display_command, "needs_shell": False, "kind": spec.kind}})
            code, out, err = run_capture(spec.argv)
            return _json(self, 200, {"ok": True, "returncode": code, "stdout": out, "stderr": err,
                                     "spec": {"argv": spec.argv, "explanation": spec.explanation,
                                              "display_command": spec.display_command,
                                              "needs_shell": spec.needs_shell, "kind": spec.kind}})
        return self.send_error(404, "Not found")

    def do_PUT(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/shortcuts/"):
            shortcut_id = parsed.path[len("/api/shortcuts/"):]
            if "/" in shortcut_id or not shortcut_id:
                return self.send_error(400, "Bad id")
            data = _read_json_body(self)
            sc, errors = self.store.update(shortcut_id, data)
            if errors:
                status = 404 if errors == ["Shortcut not found."] else 400
                return _json(self, status, {"errors": errors})
            return _json(self, 200, {"shortcut": sc.to_dict()})
        return self.send_error(404, "Not found")

    def do_PATCH(self):
        return self.do_PUT()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/shortcuts/"):
            shortcut_id = parsed.path[len("/api/shortcuts/"):]
            if self.store.delete(shortcut_id):
                return _json(self, 200, {"ok": True})
            return _json(self, 404, {"errors": ["Shortcut not found."]})
        return self.send_error(404, "Not found")


def serve(port: int = 8765, data_dir=None) -> ThreadingHTTPServer:
    Handler.store = ShortcutStore(data_dir=data_dir)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server
