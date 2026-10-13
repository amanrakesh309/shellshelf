"""Tests for launch specs: argv separation, no interpolation, platform behavior."""

import inspect
import re

from shellshelf import launcher
from shellshelf.launcher import build_launch_spec


def test_terminal_simple_command_splits_without_shell():
    spec = build_launch_spec("ls -la /tmp", "terminal", platform="linux")
    assert spec.needs_shell is False
    assert spec.argv == ["ls", "-la", "/tmp"]


def test_arguments_not_interpolated_into_shell_string():
    # Quoted segments stay single argv elements; no shell string is built.
    spec = build_launch_spec('echo "hello world"', "terminal", platform="linux")
    assert spec.argv == ["echo", "hello world"]
    assert spec.argv != ["sh", "-c", 'echo "hello world"']


def test_shell_syntax_requires_explicit_shell():
    spec = build_launch_spec("echo $HOME | grep x", "terminal", platform="linux")
    assert spec.needs_shell is True
    assert spec.argv[:2] == ["sh", "-c"]
    assert "explicitly" in spec.explanation.lower() or "confirm" in spec.explanation.lower()


def test_app_modes_per_platform():
    assert build_launch_spec("https://example.com", "app", platform="linux").argv[0] == "xdg-open"
    assert build_launch_spec("Safari", "app", platform="macos").argv[0] == "open"


def test_no_shell_true_anywhere_and_no_elevated_privs():
    src = inspect.getsource(launcher)
    assert "shell=False" in src  # all subprocess calls are explicit shell=False
    assert re.search(r"subprocess\.\w+\(.*shell\s*=\s*True", src) is None
    assert "Popen" not in src or "shell=False" in src
    for banned in ("sudo", "pkexec", "osascript", "setuid", "chmod +s"):
        assert banned not in src.lower()


def test_rejects_empty_and_bad_mode():
    import pytest
    with pytest.raises(ValueError):
        build_launch_spec("", "terminal", platform="linux")
    with pytest.raises(ValueError):
        build_launch_spec("ls", "bogus", platform="linux")


def test_app_linux_bare_name_resolves_via_path():
    import shutil
    spec = build_launch_spec("python3 --version", "app", platform="linux")
    assert spec.needs_shell is False
    assert spec.argv[0] == shutil.which("python3")
    assert spec.argv[1:] == ["--version"]


def test_app_linux_unknown_name_is_actionable_error():
    import pytest
    with pytest.raises(ValueError) as excinfo:
        build_launch_spec("definitely-not-an-installed-app-xyz", "app", platform="linux")
    assert "not found on PATH" in str(excinfo.value)


def test_app_linux_urls_and_paths_keep_opener():
    assert build_launch_spec("https://example.com", "app", platform="linux").argv == ["xdg-open", "https://example.com"]
    assert build_launch_spec("/usr/share/doc", "app", platform="linux").argv == ["xdg-open", "/usr/share/doc"]


def test_app_macos_names_use_open_dash_a():
    spec = build_launch_spec("Safari", "app", platform="macos")
    assert spec.argv == ["open", "-a", "Safari"]
    assert build_launch_spec("https://example.com", "app", platform="macos").argv == ["open", "https://example.com"]
