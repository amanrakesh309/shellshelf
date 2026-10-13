"""Safe alias import: parse text only. Never sources, executes, or modifies rc files.

Supported: single-line ``alias name='value'`` / ``alias name="value"`` /
``alias name=value`` where *value* has no shell metacharacters.
Everything else is skipped with a human-readable reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ALIAS_RE = re.compile(
    r"""^\s*alias\s+              # leading 'alias' keyword
        (?P<name>[A-Za-z_][A-Za-z0-9_\-]*)  # alias name
        \s*=\s*
        (?P<value>.+?)               # raw value
        \s*$""",
    re.VERBOSE,
)

# Characters that prove the value needs a real shell (or is code, not a
# straightforward command). Any value containing these is skipped.
UNSAFE_CHARS = set("$`!*?~#(){}[]<>|&;\\")
# Multi-char operators that are unsafe even though some chars above cover them.
UNSAFE_SEQUENCES = ("$(", "${", "$((", "&&", "||", ">>", "<<", "`")


@dataclass
class ParsedAlias:
    name: str
    command: str
    line_no: int


@dataclass
class SkippedLine:
    line_no: int
    line: str
    reason: str


def _unquote(raw: str) -> tuple[str | None, str | None]:
    """Return (unquoted, error_reason). Pure string handling, no execution."""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        inner = raw[1:-1]
        if "'" in inner:
            return None, "unbalanced single quotes"
        return inner, None
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        inner = raw[1:-1]
        # Inside double quotes a $ or backtick would expand in a shell.
        if '"' in inner.replace('\\"', ""):
            return None, "unbalanced double quotes"
        return inner, None
    # Unquoted: must be a single token with no quotes/spaces.
    if not raw or any(c in raw for c in ("'", '"', " ", "\t")):
        return None, "unbalanced or missing quotes"
    return raw, None


def _check_safe(command: str) -> str | None:
    """Return reason string if unsafe, else None."""
    if not command.strip():
        return "empty command"
    if "\n" in command or "\x00" in command:
        return "multi-line or null byte"
    for seq in UNSAFE_SEQUENCES:
        if seq in command:
            return f"contains shell syntax '{seq}' (command substitution, chaining, or redirection)"
    found = sorted({c for c in command if c in UNSAFE_CHARS})
    if found:
        shown = " ".join(f"'{c}'" for c in found)
        return f"contains shell metacharacter(s) {shown} — import only plain commands"
    lowered = command.strip().lower()
    for keyword in ("sudo ", "doas ", "su ", "eval ", "exec ", "source ", ". "):
        if lowered.startswith(keyword):
            return f"starts with '{keyword.strip()}' — privileged/evaluating commands are not auto-imported"
    return None


def parse_alias_text(text: str, origin: str = "paste") -> tuple[list[ParsedAlias], list[SkippedLine]]:
    """Parse alias declarations from *text* without executing anything."""
    entries: list[ParsedAlias] = []
    skipped: list[SkippedLine] = []
    seen: set[str] = set()
    for i, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        display = raw_line.strip()
        if len(display) > 200:
            display = display[:200] + "…"
        if not line or line.startswith("#"):
            continue
        match = ALIAS_RE.match(raw_line)
        if not match:
            skipped.append(SkippedLine(i, display, "not a simple 'alias name=value' declaration — skipped"))
            continue
        name = match.group("name")
        value_raw = match.group("value").strip()
        # Strip trailing inline comment only when outside quotes: simplest safe
        # approach is to require the value to end with a quote if it starts with one.
        command, err = _unquote(value_raw)
        if err is not None or command is None:
            skipped.append(SkippedLine(i, display, f"malformed declaration ({err}) — skipped"))
            continue
        if not command.strip():
            skipped.append(SkippedLine(i, display, "empty command — skipped"))
            continue
        unsafe_reason = _check_safe(command)
        if unsafe_reason is not None:
            skipped.append(SkippedLine(i, display, f"{unsafe_reason} — skipped"))
            continue
        if name in seen:
            skipped.append(SkippedLine(i, display, f"duplicate alias '{name}' in the same file — skipped"))
            continue
        seen.add(name)
        entries.append(ParsedAlias(name=name, command=command.strip(), line_no=i))
    return entries, skipped


def read_alias_file(path: str) -> str:
    """Read a shell rc file as plain text. Never sources or executes it."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


CANDIDATE_FILES = (
    ("~/.zshrc", "Zsh"),
    ("~/.zprofile", "Zsh login (macOS)"),
    ("~/.bashrc", "Bash (Linux)"),
    ("~/.bash_profile", "Bash login (macOS/Linux)"),
    ("~/.profile", "POSIX login shell"),
)
