"""Backward-compat tests for v1 -> v2 recent_files migration."""

from __future__ import annotations

import json

from utils.recent_files import (
    add_recent_input,
    load_recent_files,
    _store_path,
)


def _write_v1(data: dict):
    p = _store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


# ---------- 1. migrate v1 single entry ----------

def test_migrate_v1_single_entry():
    _write_v1({
        "saved_at": "2026-04-01T10:00:00",
        "input": {"name": "old_in.csv", "path": "/p/old_in.csv"},
        "gps":   {"name": "old_gps.csv", "path": "/p/old_gps.csv"},
    })
    data = load_recent_files()
    assert data["version"] == 2
    assert len(data["input"]) == 1
    assert len(data["gps"]) == 1
    assert data["input"][0]["name"] == "old_in.csv"
    assert data["input"][0]["path"] == "/p/old_in.csv"
    assert data["gps"][0]["name"] == "old_gps.csv"


# ---------- 2. preserves last_used from saved_at ----------

def test_migrate_v1_preserves_last_used_from_saved_at():
    _write_v1({
        "saved_at": "2026-04-01T10:00:00",
        "input": {"name": "x.csv", "path": "/p/x.csv"},
        "gps": None,
    })
    data = load_recent_files()
    assert data["input"][0]["last_used"] == "2026-04-01T10:00:00"


# ---------- 3. handles null fields ----------

def test_migrate_v1_handles_null_fields():
    _write_v1({
        "saved_at": "2026-04-01T10:00:00",
        "input": None,
        "gps": None,
    })
    data = load_recent_files()
    assert data["input"] == []
    assert data["gps"] == []


# ---------- 4. doesn't overwrite v1 on disk until mutation ----------

def test_migrate_v1_does_not_overwrite_disk_until_mutation(make_csv):
    _write_v1({
        "saved_at": "2026-04-01T10:00:00",
        "input": {"name": "x.csv", "path": "/p/x.csv"},
        "gps": None,
    })
    raw_before = _store_path().read_text()
    load_recent_files()
    raw_after_load = _store_path().read_text()
    assert raw_before == raw_after_load  # disk untouched on read

    p = make_csv("new.csv")
    add_recent_input(p)
    raw_after_mutation = json.loads(_store_path().read_text())
    assert raw_after_mutation["version"] == 2  # now v2
