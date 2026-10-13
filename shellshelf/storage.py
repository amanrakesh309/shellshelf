"""JSON-file storage in the app's own data dir (never touches shell rc files)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .model import Shortcut, normalize_shortcut_payload, validate_shortcut


def default_data_dir() -> Path:
    override = os.environ.get("SHELLSHELF_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ShellShelf"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "shellshelf"


class ShortcutStore:
    """CRUD + search + favorites over a single JSON file."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.file = self.data_dir / "shortcuts.json"
        self._items: dict[str, Shortcut] = {}
        self.load()

    # -- persistence -----------------------------------------------------
    def load(self) -> None:
        self._items = {}
        if not self.file.exists():
            return
        try:
            raw = json.loads(self.file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt file: keep empty in memory; do not crash. Save will overwrite
            # only on a successful mutating operation.
            raw = []
        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict):
                    try:
                        sc = Shortcut.from_dict(entry)
                    except (TypeError, ValueError):
                        continue
                    self._items[sc.id] = sc

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        payload = [s.to_dict() for s in self._items.values()]
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.file)

    # -- queries ---------------------------------------------------------
    def list(self, query: str = "", favorites_only: bool = False) -> list[Shortcut]:
        q = query.strip().lower()
        out = list(self._items.values())
        if favorites_only:
            out = [s for s in out if s.favorite]
        if q:
            out = [s for s in out if q in s.name.lower() or q in s.command.lower()]
        out.sort(key=lambda s: (not s.favorite, s.name.lower()))
        return out

    def get(self, shortcut_id: str) -> Shortcut | None:
        return self._items.get(shortcut_id)

    def name_exists(self, name: str, exclude_id: str | None = None) -> bool:
        lowered = name.strip().lower()
        return any(s.name.strip().lower() == lowered and s.id != exclude_id for s in self._items.values())

    # -- mutations -------------------------------------------------------
    def add(self, payload: dict) -> tuple[Shortcut | None, list[str]]:
        data = normalize_shortcut_payload(payload)
        errors = validate_shortcut(data)
        if not errors and self.name_exists(data["name"]):
            errors.append(f"A shortcut named '{data['name'].strip()}' already exists.")
        if errors:
            return None, errors
        sc = Shortcut(
            name=data["name"].strip(),
            command=data["command"].strip(),
            launch_mode=data.get("launch_mode", "terminal"),
            source=data.get("source", "manual"),
            description=data.get("description", ""),
            favorite=bool(data.get("favorite", False)),
        )
        self._items[sc.id] = sc
        self._save()
        return sc, []

    def update(self, shortcut_id: str, payload: dict) -> tuple[Shortcut | None, list[str]]:
        existing = self._items.get(shortcut_id)
        if existing is None:
            return None, ["Shortcut not found."]
        merged = existing.to_dict()
        for key in ("name", "command", "launch_mode", "source", "description", "favorite"):
            if key in payload:
                merged[key] = payload[key]
        merged = normalize_shortcut_payload(merged)
        errors = validate_shortcut(merged)
        if not errors and self.name_exists(merged["name"], exclude_id=shortcut_id):
            errors.append(f"A shortcut named '{merged['name'].strip()}' already exists.")
        if errors:
            return None, errors
        updated = Shortcut.from_dict({**merged, "id": shortcut_id})
        self._items[shortcut_id] = updated
        self._save()
        return updated, []

    def delete(self, shortcut_id: str) -> bool:
        if shortcut_id not in self._items:
            return False
        del self._items[shortcut_id]
        self._save()
        return True

    def set_favorite(self, shortcut_id: str, favorite: bool) -> Shortcut | None:
        sc = self._items.get(shortcut_id)
        if sc is None:
            return None
        sc.favorite = bool(favorite)
        self._save()
        return sc
