"""Shortcut model and validation (pure stdlib, no I/O)."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field

MAX_NAME_LEN = 100
MAX_COMMAND_LEN = 2000
MAX_DESC_LEN = 500
VALID_LAUNCH_MODES = ("terminal", "app")
NAME_RE = re.compile(r"^[A-Za-z0-9 _\-\.]{1,100}$")


@dataclass
class Shortcut:
    """A user-owned launcher entry. Never executes on creation."""

    name: str
    command: str
    launch_mode: str = "terminal"
    source: str = "manual"
    description: str = ""
    favorite: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Shortcut":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            name=str(data.get("name", "")),
            command=str(data.get("command", "")),
            launch_mode=str(data.get("launch_mode", "terminal")),
            source=str(data.get("source", "manual")),
            description=str(data.get("description", "")),
            favorite=bool(data.get("favorite", False)),
        )


def validate_shortcut(data: dict) -> list[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    errors: list[str] = []
    name = str(data.get("name", "")).strip()
    command = str(data.get("command", "")).strip()
    launch_mode = str(data.get("launch_mode", "terminal"))
    description = str(data.get("description", ""))
    source = str(data.get("source", "manual")).strip()

    if not name:
        errors.append("Name is required.")
    elif len(name) > MAX_NAME_LEN:
        errors.append(f"Name must be {MAX_NAME_LEN} characters or fewer.")
    elif not NAME_RE.match(name):
        errors.append("Name may only contain letters, numbers, spaces, '-', '_' and '.'.")

    if not command:
        errors.append("Command is required.")
    elif len(command) > MAX_COMMAND_LEN:
        errors.append(f"Command must be {MAX_COMMAND_LEN} characters or fewer.")
    elif "\n" in command or "\x00" in command:
        errors.append("Command must be a single line without null bytes.")

    if launch_mode not in VALID_LAUNCH_MODES:
        errors.append("Launch mode must be 'terminal' or 'app'.")

    if len(description) > MAX_DESC_LEN:
        errors.append(f"Description must be {MAX_DESC_LEN} characters or fewer.")

    if not source:
        errors.append("Source is required.")
    elif len(source) > 200:
        errors.append("Source must be 200 characters or fewer.")

    return errors


def normalize_shortcut_payload(data: dict) -> dict:
    """Trim strings and coerce types before validation/storage."""
    out = dict(data)
    for key in ("name", "command", "source", "description", "launch_mode"):
        if key in out and out[key] is not None:
            out[key] = str(out[key]).strip() if key != "description" else str(out[key]).strip()
    if "favorite" in out:
        out["favorite"] = bool(out["favorite"])
    if "launch_mode" not in out or not out["launch_mode"]:
        out["launch_mode"] = "terminal"
    if "source" not in out or not out["source"]:
        out["source"] = "manual"
    return out
