"""Build a stdlib-only single-file distributable: `python3 packaging/build.py`.

Produces `dist/shellshelf.pyz` (runnable with any Python 3.10+ as
`python3 dist/shellshelf.pyz`). Only stdlib is used; nothing is installed.
"""

from __future__ import annotations

import shutil
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "dist" / "shellshelf.pyz"

INCLUDE_TOP = {"app.py", "__main__.py"}
INCLUDE_DIRS = {"shellshelf", "static"}


def _filter(path: Path) -> bool:
    # zipapp passes paths relative to the source root (e.g. Path('.git')).
    parts = path.parts
    if not parts or parts[0] in (".", ""):
        parts = parts[1:]
        if not parts:
            return True
    if parts[0] in INCLUDE_DIRS:
        return "__pycache__" not in parts
    return len(parts) == 1 and parts[0] in INCLUDE_TOP


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # Build outside the source tree: zipapp refuses targets inside source.
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "shellshelf.pyz"
        zipapp.create_archive(str(ROOT), str(staged), interpreter="/usr/bin/env python3", filter=_filter)
        shutil.move(str(staged), str(TARGET))
    print(f"Built {TARGET} ({TARGET.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
