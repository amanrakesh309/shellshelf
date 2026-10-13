"""Launch layer: explicit, testable, no shell interpolation by default."""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass

SHELL_SYNTAX_CHARS = set("$`!*?~#(){}[]<>|&;\\")
_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


@dataclass
class LaunchSpec:
    kind: str  # "terminal" | "app"
    argv: list[str]
    needs_shell: bool
    explanation: str
    display_command: str


def get_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def detect_shell_syntax(command: str) -> bool:
    return any(c in SHELL_SYNTAX_CHARS for c in command) or "$(" in command or "${" in command


def is_url(target: str) -> bool:
    """True for `scheme://...` targets (opened, never executed)."""
    return _URL_RE.match(target.strip()) is not None


def is_path_like(target: str) -> bool:
    """True for absolute paths, `~/...`, `./...`, or anything containing `/`."""
    t = target.strip()
    return t.startswith(("/", "~", "./", "../")) or "/" in t


def build_app_spec(command: str, platform: str | None = None) -> LaunchSpec:
    """Build an `app`-mode spec that actually launches installed apps.

    - URLs and path-like targets go through the platform opener
      (`xdg-open` on Linux, `open` on macOS) as a single separate argument.
    - Bare app names: Linux resolves via `shutil.which` (PATH) and execs the
      resolved binary directly (no shell); macOS uses `open -a <name>`.
    Raises ValueError with an actionable message when unresolvable.
    Never launches anything.
    """
    platform = platform or get_platform()
    cmd = command.strip()
    if not cmd:
        raise ValueError("Command is empty.")
    if "\x00" in cmd or "\n" in cmd:
        raise ValueError("Command must be a single line.")

    if platform == "macos":
        if is_url(cmd) or is_path_like(cmd) or os.path.exists(os.path.expanduser(cmd)):
            return LaunchSpec(
                kind="app",
                argv=["open", cmd],
                needs_shell=False,
                explanation="Opens the URL/file with macOS 'open'; target passed as a separate argument (no shell).",
                display_command=cmd,
            )
        return LaunchSpec(
            kind="app",
            argv=["open", "-a", cmd],
            needs_shell=False,
            explanation="Launches the installed macOS application via 'open -a' (no shell).",
            display_command=cmd,
        )

    if platform == "linux":
        if is_url(cmd) or is_path_like(cmd) or os.path.exists(os.path.expanduser(cmd)):
            return LaunchSpec(
                kind="app",
                argv=["xdg-open", cmd],
                needs_shell=False,
                explanation="Opens the URL/file with 'xdg-open'; target passed as a separate argument (no shell).",
                display_command=cmd,
            )
        try:
            parts = shlex.split(cmd, posix=True)
        except ValueError as exc:
            raise ValueError(f"Could not parse application target without a shell: {exc}") from exc
        resolved = shutil.which(parts[0]) if parts else None
        if resolved is None:
            raise ValueError(
                f"Application '{parts[0] if parts else cmd}' was not found on PATH and is not a URL or file path. "
                "Install it, use its full path/URL, or switch to 'Run command' mode."
            )
        return LaunchSpec(
            kind="app",
            argv=[resolved, *parts[1:]],
            needs_shell=False,
            explanation="Launches the resolved executable directly with arguments passed separately (no shell).",
            display_command=cmd,
        )

    return LaunchSpec(
        kind="app",
        argv=[cmd],
        needs_shell=False,
        explanation="Unsupported platform: target is shown so you can open it manually.",
        display_command=cmd,
    )


def build_launch_spec(command: str, launch_mode: str, platform: str | None = None) -> LaunchSpec:
    """Build an argv list without interpolating into a shell string.

    Raises ValueError on empty/unsupported input. Never launches anything.
    """
    platform = platform or get_platform()
    cmd = command.strip()
    if not cmd:
        raise ValueError("Command is empty.")
    if launch_mode not in ("terminal", "app"):
        raise ValueError("Launch mode must be 'terminal' or 'app'.")
    if "\x00" in cmd or "\n" in cmd:
        raise ValueError("Command must be a single line.")

    if launch_mode == "app":
        return build_app_spec(cmd, platform)

    # launch_mode == "terminal": prefer direct argv split, no shell.
    if detect_shell_syntax(cmd):
        return LaunchSpec(
            kind="terminal",
            argv=["sh", "-c", cmd],
            needs_shell=True,
            explanation=(
                "This command contains shell syntax and can only run through 'sh -c'. "
                "It will run only after you explicitly confirm, and output/errors are shown."
            ),
            display_command=cmd,
        )
    try:
        argv = shlex.split(cmd, posix=True)
    except ValueError as exc:
        raise ValueError(f"Could not parse command without a shell: {exc}") from exc
    if not argv:
        raise ValueError("Command is empty.")
    return LaunchSpec(
        kind="terminal",
        argv=argv,
        needs_shell=False,
        explanation="Runs directly with arguments passed separately (no shell interpolation).",
        display_command=cmd,
    )


def run_capture(argv: list[str], timeout: int = 15) -> tuple[int, str, str]:
    """Run argv with shell=False and capture output. No shell string built."""
    if not argv:
        raise ValueError("argv must not be empty.")
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, shell=False)
        return proc.returncode, proc.stdout[-4000:], proc.stderr[-4000:]
    except FileNotFoundError as exc:
        return 127, "", f"Executable not found: {exc}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Timed out after {timeout}s."
    except OSError as exc:
        return 1, "", f"Failed to launch: {exc}"
