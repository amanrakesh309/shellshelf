"""Tests for safe alias parsing: quotes, malformed, duplicates, metachars, no-exec."""

import os
import tempfile

from shellshelf import alias_parser
from shellshelf.alias_parser import parse_alias_text


def test_single_and_double_quotes():
    text = "alias ll='ls -la'\n" 'alias gs="git status"\n' "alias p=python3\n"
    entries, skipped = parse_alias_text(text)
    assert skipped == []
    assert {e.name: e.command for e in entries} == {
        "ll": "ls -la", "gs": "git status", "p": "python3",
    }


def test_malformed_skipped_with_reasons():
    text = "alias broken='oops\n" "alias empty=''\n" "not an alias at all\n" "export FOO=bar\n"
    entries, skipped = parse_alias_text(text)
    assert entries == []
    assert len(skipped) == 4
    assert all(s.reason for s in skipped)


def test_duplicates_within_file():
    text = "alias a='ls'\nalias a='pwd'\n"
    entries, skipped = parse_alias_text(text)
    assert len(entries) == 1
    assert len(skipped) == 1
    assert "duplicate" in skipped[0].reason


def test_shell_metacharacters_rejected():
    evil = [
        "alias a='echo $(whoami)'",
        "alias b='echo `id`'",
        "alias c='a; rm -rf /'",
        "alias d='a | grep b'",
        "alias e='a && b'",
        "alias f='echo $HOME'",
        "alias g='cat < /etc/passwd'",
        "alias h='sudo apt update'",
    ]
    entries, skipped = parse_alias_text("\n".join(evil))
    assert entries == []
    assert len(skipped) == len(evil)


def test_functions_and_conditionals_skipped():
    text = "myfunc() { echo hi; }\n" "if [ x ]; then alias q='x'; fi\n" "alias ok='ls -la'\n"
    entries, skipped = parse_alias_text(text)
    assert [e.name for e in entries] == ["ok"]
    assert len(skipped) == 2


def test_parsing_never_executes(tmp_path=None):
    # A canary file: if parsing executed content, this file would appear.
    with tempfile.TemporaryDirectory() as tmp:
        canary = os.path.join(tmp, "pwned")
        text = f"alias x='touch {canary}'\n"
        entries, skipped = parse_alias_text(text)
        # 'touch /tmp/...' has no metachars so it parses, but nothing must run.
        assert not os.path.exists(canary)
        # Parser module itself never calls subprocess/os.system/eval/exec.
        import inspect
        src = inspect.getsource(alias_parser)
        for banned in ("subprocess", "os.system", "os.popen", "eval(", "exec("):
            assert banned not in src
