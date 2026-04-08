"""Session save/restore for EntropyMax.

Stores the working session state (file paths, K value, group relabeling,
colors, sample selection, analysis params) in a persistent JSON file
under the cache root, separate from the volatile cache subdir.

Schema v1:
    {
        "version": 1,
        "saved_at": "ISO timestamp",
        "state": {... user state ...}
    }
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .cache_paths import ensure_cache_root

_SCHEMA_VERSION = 1
SESSION_FILENAME = "session.json"

REQUIRED_KEYS = {"input_file_path", "gps_file_path"}
OPTIONAL_KEYS = {
    "selected_k_for_details",
    "group_relabel_mapping",
    "group_colors",
    "selected_samples",
    "analysis_params",
}


def _store_path() -> Path:
    return ensure_cache_root() / SESSION_FILENAME


def _coerce(value: Any) -> Any:
    """Recursively coerce non-JSON-native values into JSON-serializable equivalents."""
    if isinstance(value, dict):
        return {str(k): _coerce(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [_coerce(v) for v in sorted(value, key=lambda x: str(x))]
    if isinstance(value, tuple):
        return [_coerce(v) for v in value]
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Fallback: stringify (e.g. QColor, Path)
    return str(value)


def _atomic_write_json(path: Path, data: dict) -> None:
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


def save_session(state: dict) -> None:
    """Persist the session state. Raises ValueError if required keys missing."""
    missing = REQUIRED_KEYS - set(state.keys())
    if missing:
        raise ValueError(f"Missing required session keys: {sorted(missing)}")
    payload = {
        "version": _SCHEMA_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "state": _coerce(state),
    }
    _atomic_write_json(_store_path(), payload)


def load_session() -> Optional[dict]:
    """Load session state. Returns None if missing, malformed, or wrong version."""
    path = _store_path()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("version") != _SCHEMA_VERSION:
        return None
    state = payload.get("state")
    if not isinstance(state, dict):
        return None
    return state


def clear_session() -> None:
    """Delete the session file if it exists. Idempotent."""
    path = _store_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def is_session_restorable(state: dict) -> tuple[bool, list[str]]:
    """Check whether all referenced files in the session still exist on disk."""
    missing: list[str] = []
    for key in ("input_file_path", "gps_file_path"):
        path = state.get(key)
        if path and not os.path.exists(path):
            missing.append(path)
    return (len(missing) == 0, missing)
