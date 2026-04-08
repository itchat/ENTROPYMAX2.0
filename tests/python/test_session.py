"""Unit tests for the session save/restore module."""

from __future__ import annotations

import json

import pytest

from utils.session import (
    REQUIRED_KEYS,
    clear_session,
    is_session_restorable,
    load_session,
    save_session,
    _store_path,
)


def _minimal_state(input_path: str = "/tmp/in.csv", gps_path: str = "/tmp/gps.csv") -> dict:
    return {"input_file_path": input_path, "gps_file_path": gps_path}


# ---------- 1. load_session_absent_returns_none ----------

def test_load_session_absent_returns_none():
    assert load_session() is None


# ---------- 2. save_then_load_roundtrip ----------

def test_save_then_load_roundtrip():
    state = {
        "input_file_path": "/tmp/a.csv",
        "gps_file_path": "/tmp/b.csv",
        "selected_k_for_details": 5,
        "group_relabel_mapping": {0: 1, 1: 2},
        "group_colors": {1: "#ff0000", 2: "#00ff00"},
        "selected_samples": ["S1", "S2"],
        "analysis_params": {"do_permutations": True, "k_min": 2, "k_max": 10},
    }
    save_session(state)
    loaded = load_session()
    assert loaded is not None
    assert loaded["input_file_path"] == "/tmp/a.csv"
    assert loaded["gps_file_path"] == "/tmp/b.csv"
    assert loaded["selected_k_for_details"] == 5
    assert loaded["selected_samples"] == ["S1", "S2"]
    assert loaded["analysis_params"]["k_max"] == 10


# ---------- 3. save_rejects_missing_required_keys ----------

def test_save_rejects_missing_required_keys():
    with pytest.raises(ValueError):
        save_session({"input_file_path": "/tmp/a.csv"})  # missing gps


# ---------- 4. save_coerces_sets_to_lists ----------

def test_save_coerces_sets_to_lists():
    state = _minimal_state()
    state["selected_samples"] = {"S1", "S2", "S3"}
    save_session(state)
    loaded = load_session()
    assert isinstance(loaded["selected_samples"], list)
    assert sorted(loaded["selected_samples"]) == ["S1", "S2", "S3"]


# ---------- 5. save_coerces_nested_tuples ----------

def test_save_coerces_nested_tuples():
    state = _minimal_state()
    state["group_colors"] = {1: ("#ff0000", "tag")}
    save_session(state)
    loaded = load_session()
    # JSON has no tuples; should round-trip as list
    assert loaded["group_colors"]["1"] == ["#ff0000", "tag"]


# ---------- 6. load_returns_none_on_malformed_json ----------

def test_load_returns_none_on_malformed_json():
    _store_path().parent.mkdir(parents=True, exist_ok=True)
    _store_path().write_text("not json {{{")
    assert load_session() is None


# ---------- 7. load_returns_none_on_schema_mismatch ----------

def test_load_returns_none_on_schema_mismatch():
    _store_path().parent.mkdir(parents=True, exist_ok=True)
    _store_path().write_text(json.dumps({"version": 99, "state": {}}))
    assert load_session() is None


# ---------- 8. clear_session_removes_file ----------

def test_clear_session_removes_file():
    save_session(_minimal_state())
    assert _store_path().exists()
    clear_session()
    assert not _store_path().exists()


# ---------- 9. clear_session_idempotent_when_absent ----------

def test_clear_session_idempotent_when_absent():
    clear_session()  # should not raise
    clear_session()


# ---------- 10. is_session_restorable_true_when_files_exist ----------

def test_is_session_restorable_true_when_files_exist(make_csv):
    state = {
        "input_file_path": make_csv("in.csv"),
        "gps_file_path": make_csv("gps.csv"),
    }
    ok, missing = is_session_restorable(state)
    assert ok is True
    assert missing == []


# ---------- 11. is_session_restorable_false_lists_missing_paths ----------

def test_is_session_restorable_false_lists_missing_paths(make_csv):
    in_path = make_csv("in.csv")
    state = {
        "input_file_path": in_path,
        "gps_file_path": "/nonexistent/missing.csv",
    }
    ok, missing = is_session_restorable(state)
    assert ok is False
    assert "/nonexistent/missing.csv" in missing


# ---------- 12. atomic_write_does_not_corrupt_on_failure ----------

def test_atomic_write_does_not_corrupt_on_failure(monkeypatch):
    save_session(_minimal_state("/tmp/orig.csv", "/tmp/orig_gps.csv"))
    original = _store_path().read_bytes()

    monkeypatch.setattr("os.replace", lambda *a, **k: (_ for _ in ()).throw(OSError("fail")))
    with pytest.raises(OSError):
        save_session(_minimal_state("/tmp/new.csv", "/tmp/new_gps.csv"))

    assert _store_path().read_bytes() == original
