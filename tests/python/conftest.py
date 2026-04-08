"""Shared fixtures for ENTROPYMAX2.0 frontend tests."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Inject frontend/ on sys.path so `from utils.recent_files import ...` works
_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND = _REPO_ROOT / "frontend"
if str(_FRONTEND) not in sys.path:
    sys.path.insert(0, str(_FRONTEND))

# QtWebEngineWidgets must be imported BEFORE QApplication is created
try:
    from PyQt6 import QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass


@pytest.fixture(autouse=True)
def tmp_cache_root(tmp_path, monkeypatch):
    """Redirect EntropyMax cache to a temp dir so tests never touch real cache."""
    cache_dir = tmp_path / "entro_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ENTROPYMAX_CACHE_DIR", str(cache_dir))
    yield cache_dir


@pytest.fixture
def frozen_now():
    """Return a callable that produces a fixed-then-incrementing datetime."""
    state = {"counter": 0}

    def _make(seconds_offset: int = 0) -> datetime:
        state["counter"] += 1
        return datetime(2026, 4, 8, 12, 0, 0 + seconds_offset)

    return _make


@pytest.fixture
def make_csv(tmp_path):
    """Factory: create a dummy CSV file at tmp_path/<name> and return its path string."""
    def _factory(name: str = "sample.csv", content: str = "a,b\n1,2\n") -> str:
        p = tmp_path / name
        p.write_text(content)
        return str(p)
    return _factory
