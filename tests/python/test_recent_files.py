"""Unit tests for the new list-based recent files API."""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from utils.recent_files import (
    MAX_ENTRIES,
    add_recent_gps,
    add_recent_input,
    list_recent_gps,
    list_recent_inputs,
    load_recent_files,
    save_recent_files,
    _store_path,
)


# ---------- 1. load_empty_returns_skeleton ----------

def test_load_empty_returns_skeleton():
    data = load_recent_files()
    assert data == {"version": 2, "input": [], "gps": []}


# ---------- 2. add_recent_input_creates_entry ----------

def test_add_recent_input_creates_entry(make_csv, frozen_now):
    p = make_csv("a.csv")
    data = add_recent_input(p, now=frozen_now())
    assert len(data["input"]) == 1
    entry = data["input"][0]
    assert entry["name"] == "a.csv"
    assert entry["path"] == os.path.abspath(p)
    assert "last_used" in entry


# ---------- 3. add_recent_input_dedupes_by_path ----------

def test_add_recent_input_dedupes_by_path(make_csv):
    p = make_csv("a.csv")
    add_recent_input(p, now=datetime(2026, 4, 8, 12, 0, 0))
    add_recent_input(p, now=datetime(2026, 4, 8, 12, 0, 5))
    data = load_recent_files()
    assert len(data["input"]) == 1
    assert data["input"][0]["last_used"] == "2026-04-08T12:00:05"


# ---------- 4. add_recent_input_prepends_newest ----------

def test_add_recent_input_prepends_newest(make_csv):
    a = make_csv("a.csv")
    b = make_csv("b.csv")
    c = make_csv("c.csv")
    add_recent_input(a, now=datetime(2026, 4, 8, 12, 0, 0))
    add_recent_input(b, now=datetime(2026, 4, 8, 12, 0, 1))
    add_recent_input(c, now=datetime(2026, 4, 8, 12, 0, 2))
    data = load_recent_files()
    names = [e["name"] for e in data["input"]]
    assert names == ["c.csv", "b.csv", "a.csv"]


# ---------- 5. add_recent_input_caps_at_five ----------

def test_add_recent_input_caps_at_five(tmp_path):
    paths = []
    for i in range(7):
        p = tmp_path / f"f{i}.csv"
        p.write_text("x")
        paths.append(str(p))
    for i, p in enumerate(paths):
        add_recent_input(p, now=datetime(2026, 4, 8, 12, 0, i))
    data = load_recent_files()
    assert len(data["input"]) == MAX_ENTRIES == 5
    names = [e["name"] for e in data["input"]]
    assert names == ["f6.csv", "f5.csv", "f4.csv", "f3.csv", "f2.csv"]


# ---------- 6. gps independent of inputs ----------

def test_add_recent_gps_is_independent_of_inputs(make_csv):
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    add_recent_input(in_path, now=datetime(2026, 4, 8, 12, 0, 0))
    add_recent_gps(gps_path, now=datetime(2026, 4, 8, 12, 0, 1))
    data = load_recent_files()
    assert len(data["input"]) == 1
    assert len(data["gps"]) == 1
    assert data["input"][0]["name"] == "in.csv"
    assert data["gps"][0]["name"] == "gps.csv"


# ---------- 7. list filters missing files ----------

def test_list_recent_inputs_filters_missing_files(tmp_path):
    a = tmp_path / "a.csv"; a.write_text("x")
    b = tmp_path / "b.csv"; b.write_text("x")
    c = tmp_path / "c.csv"; c.write_text("x")
    add_recent_input(str(a), now=datetime(2026, 4, 8, 12, 0, 0))
    add_recent_input(str(b), now=datetime(2026, 4, 8, 12, 0, 1))
    add_recent_input(str(c), now=datetime(2026, 4, 8, 12, 0, 2))
    b.unlink()
    result = list_recent_inputs()
    names = [e["name"] for e in result]
    assert names == ["c.csv", "a.csv"]


# ---------- 8. list persists prune ----------

def test_list_recent_inputs_persists_prune(tmp_path):
    a = tmp_path / "a.csv"; a.write_text("x")
    b = tmp_path / "b.csv"; b.write_text("x")
    add_recent_input(str(a), now=datetime(2026, 4, 8, 12, 0, 0))
    add_recent_input(str(b), now=datetime(2026, 4, 8, 12, 0, 1))
    a.unlink()
    list_recent_inputs()  # triggers prune + persist
    raw = json.loads(_store_path().read_text())
    assert len(raw["input"]) == 1
    assert raw["input"][0]["name"] == "b.csv"


# ---------- 9. atomic write doesn't corrupt on failure ----------

def test_save_is_atomic_on_replace_failure(make_csv, monkeypatch):
    p = make_csv("a.csv")
    add_recent_input(p, now=datetime(2026, 4, 8, 12, 0, 0))
    original = _store_path().read_bytes()

    monkeypatch.setattr("os.replace", lambda *a, **k: (_ for _ in ()).throw(OSError("fail")))
    with pytest.raises(OSError):
        save_recent_files({"version": 2, "input": [], "gps": []})

    assert _store_path().read_bytes() == original


# ---------- 10. malformed json returns skeleton ----------

def test_malformed_json_returns_skeleton():
    _store_path().parent.mkdir(parents=True, exist_ok=True)
    _store_path().write_text("not valid json {{{")
    data = load_recent_files()
    assert data == {"version": 2, "input": [], "gps": []}
