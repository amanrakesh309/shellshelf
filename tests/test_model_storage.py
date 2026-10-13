"""Tests for shortcut validation and JSON storage."""

import tempfile
from pathlib import Path

from shellshelf.model import validate_shortcut
from shellshelf.storage import ShortcutStore


def _store():
    tmp = tempfile.mkdtemp()
    return ShortcutStore(data_dir=Path(tmp))


def test_add_and_persist_across_restarts():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        s1 = ShortcutStore(data_dir=d)
        sc, errors = s1.add({"name": "List files", "command": "ls -la", "launch_mode": "terminal"})
        assert errors == []
        assert sc is not None
        # New instance over same dir sees the entry (persistence).
        s2 = ShortcutStore(data_dir=d)
        items = s2.list()
        assert len(items) == 1
        assert items[0].name == "List files"


def test_crud_search_favorites():
    store = _store()
    store.add({"name": "List all", "command": "ls -la"})
    store.add({"name": "Disk", "command": "df -h", "favorite": True})
    assert len(store.list()) == 2
    assert len(store.list(query="disk")) == 1
    assert len(store.list(favorites_only=True)) == 1
    sc = store.list()[0]
    updated, errors = store.update(sc.id, {"name": "Renamed"})
    assert errors == []
    assert updated.name == "Renamed"
    assert store.delete(sc.id) is True
    assert store.delete("missing") is False


def test_validation_rejects_bad_entries():
    assert validate_shortcut({"name": "", "command": "ls"}) != []
    assert validate_shortcut({"name": "ok", "command": ""}) != []
    assert validate_shortcut({"name": "ok", "command": "ls", "launch_mode": "bogus"}) != []
    assert validate_shortcut({"name": "x" * 101, "command": "ls"}) != []
    store = _store()
    store.add({"name": "Dup", "command": "ls"})
    _, errors = store.add({"name": "dup", "command": "pwd"})
    assert any("already exists" in e for e in errors)
