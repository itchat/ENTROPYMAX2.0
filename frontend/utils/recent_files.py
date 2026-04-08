"""Persistence helpers for two independent recent file lists (PSD + GPS).

Stores a small JSON file under the app's cache root (outside the volatile
'cache' subdir) so it survives cleanup on exit.

Schema v2:
    {
        "version": 2,
        "input": [{"name", "path", "last_used"}, ... up to MAX_ENTRIES],
        "gps":   [{"name", "path", "last_used"}, ... up to MAX_ENTRIES],
    }

Backward compatible with v1 single-entry format on read.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .cache_paths import ensure_cache_root

MAX_ENTRIES = 5
_SCHEMA_VERSION = 2


def _store_path() -> Path:
    return ensure_cache_root() / "recent_files.json"


def _empty_skeleton() -> dict:
    return {"version": _SCHEMA_VERSION, "input": [], "gps": []}


def _abs(path: str) -> str:
    return os.path.abspath(path)


def _atomic_write_json(path: Path, data: dict) -> None:
    """Write JSON atomically using a temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _migrate_v1_to_v2(old: dict) -> dict:
    """Convert legacy single-entry format to v2 list format."""
    saved_at = old.get("saved_at") or datetime.now().isoformat(timespec="seconds")
    out = _empty_skeleton()
    in_info = old.get("input")
    if isinstance(in_info, dict) and in_info.get("path"):
        out["input"].append({
            "name": in_info.get("name") or os.path.basename(in_info["path"]),
            "path": in_info["path"],
            "last_used": saved_at,
        })
    gps_info = old.get("gps")
    if isinstance(gps_info, dict) and gps_info.get("path"):
        out["gps"].append({
            "name": gps_info.get("name") or os.path.basename(gps_info["path"]),
            "path": gps_info["path"],
            "last_used": saved_at,
        })
    return out


def load_recent_files() -> dict:
    """Load recent files JSON. Returns v2 skeleton if missing/malformed.
    Auto-migrates v1 format in-memory (does NOT rewrite the file)."""
    path = _store_path()
    if not path.exists():
        return _empty_skeleton()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_skeleton()
    if not isinstance(data, dict):
        return _empty_skeleton()
    if data.get("version") == _SCHEMA_VERSION and isinstance(data.get("input"), list):
        return data
    # Legacy v1 format
    return _migrate_v1_to_v2(data)


def save_recent_files(data: dict) -> None:
    """Persist the full recent files dict atomically."""
    _atomic_write_json(_store_path(), data)


def _add_to_list(list_key: str, path: str, now: Optional[datetime]) -> dict:
    data = load_recent_files()
    target = data[list_key]
    abs_path = _abs(path)
    # Remove existing entry with same path (dedup by abspath)
    target[:] = [e for e in target if _abs(e["path"]) != abs_path]
    # Prepend new entry
    target.insert(0, {
        "name": os.path.basename(path),
        "path": abs_path,
        "last_used": (now or datetime.now()).isoformat(timespec="seconds"),
    })
    # Cap
    data[list_key] = target[:MAX_ENTRIES]
    save_recent_files(data)
    return data


def add_recent_input(path: str, *, now: Optional[datetime] = None) -> dict:
    return _add_to_list("input", path, now)


def add_recent_gps(path: str, *, now: Optional[datetime] = None) -> dict:
    return _add_to_list("gps", path, now)


def _list_with_prune(list_key: str) -> list[dict]:
    data = load_recent_files()
    original = data[list_key]
    pruned = [e for e in original if os.path.exists(e["path"])]
    if len(pruned) != len(original):
        data[list_key] = pruned
        save_recent_files(data)
    return pruned


def list_recent_inputs() -> list[dict]:
    return _list_with_prune("input")


def list_recent_gps() -> list[dict]:
    return _list_with_prune("gps")
