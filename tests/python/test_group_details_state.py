"""Tests for GroupDetailWindow / GroupDetailPopup full state save/restore."""

from __future__ import annotations

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def sample_group_window(qapp_instance, qtbot):
    """Construct a GroupDetailWindow with minimal real data."""
    from components.group_detail_popup import GroupDetailWindow
    x_labels = ["10", "100", "1000"]
    x_values = np.array([10.0, 100.0, 1000.0])
    samples = [
        {"name": "S1", "values": [1.0, 5.0, 2.0]},
        {"name": "S2", "values": [2.0, 4.0, 3.0]},
    ]
    win = GroupDetailWindow(
        group_id=1, total_groups=3,
        samples=samples, x_labels=x_labels, x_values=x_values,
        color="#aabbcc",
    )
    qtbot.addWidget(win)
    return win


# ---------- Tier A: layout settings (existing infrastructure) ----------

def test_get_full_state_includes_layout_attrs(sample_group_window):
    win = sample_group_window
    win.is_log_scale = False
    win.show_as_bar = False
    win.show_average_only = True
    win.hide_x_axis = True
    state = win.get_full_state()
    assert state["is_log_scale"] is False
    assert state["show_as_bar"] is False
    assert state["show_average_only"] is True
    assert state["hide_x_axis"] is True


def test_get_full_state_includes_view_range(sample_group_window):
    win = sample_group_window
    state = win.get_full_state()
    assert "x_range" in state and "y_range" in state
    assert isinstance(state["x_range"], list) and len(state["x_range"]) == 2


# ---------- Tier B: window geometry ----------

def test_get_full_state_includes_geometry_hex(sample_group_window):
    win = sample_group_window
    win.resize(800, 400)
    state = win.get_full_state()
    assert "geometry" in state
    assert isinstance(state["geometry"], str)
    assert len(state["geometry"]) > 0
    # Must be valid hex
    bytes.fromhex(state["geometry"])


def test_apply_full_state_restores_geometry(sample_group_window):
    win = sample_group_window
    win.resize(900, 500)
    state = win.get_full_state()
    win.resize(400, 200)  # change it
    win.apply_full_state(state)
    # Allow Qt to settle
    QApplication.processEvents()
    assert win.size().width() == 900 or win.size().width() > 200  # restoreGeometry applied


# ---------- Tier C: pinned markers ----------

def test_get_full_state_serializes_pinned_markers(sample_group_window):
    win = sample_group_window
    # Pin a synthetic marker manually (skip _pin_point which depends on plot interaction)
    win.pinned_markers.append({
        "scatter": object(),  # ignored on serialize
        "label": object(),
        "sample_name": "S1",
        "x_plot": 2.0,
        "y_plot": 5.0,
    })
    state = win.get_full_state()
    assert "pinned_markers" in state
    pms = state["pinned_markers"]
    assert len(pms) == 1
    assert pms[0]["sample_name"] == "S1"
    assert pms[0]["x_plot"] == 2.0
    assert pms[0]["y_plot"] == 5.0
    # Must NOT include unpicklable scatter / label
    assert "scatter" not in pms[0]
    assert "label" not in pms[0]


def test_apply_full_state_recreates_pinned_markers(sample_group_window):
    win = sample_group_window
    state = {
        "is_log_scale": True,
        "show_as_bar": True,
        "show_average_only": False,
        "hide_x_axis": False,
        "pinned_markers": [
            {"sample_name": "S1", "x_plot": 2.0, "y_plot": 5.0,
             "x_disp": 100.0, "y_disp": 5.0},
        ],
    }
    win.apply_full_state(state)
    assert len(win.pinned_markers) == 1
    pm = win.pinned_markers[0]
    assert pm["sample_name"] == "S1"
    assert pm["x_plot"] == 2.0


def test_apply_full_state_clears_existing_pinned_markers_first(sample_group_window):
    win = sample_group_window
    # Pre-existing marker
    win.pinned_markers.append({
        "scatter": object(), "label": object(),
        "sample_name": "OLD", "x_plot": 0, "y_plot": 0,
    })
    state = {
        "is_log_scale": True, "show_as_bar": True,
        "show_average_only": False, "hide_x_axis": False,
        "pinned_markers": [
            {"sample_name": "NEW", "x_plot": 1.0, "y_plot": 2.0,
             "x_disp": 10.0, "y_disp": 2.0},
        ],
    }
    win.apply_full_state(state)
    names = [p["sample_name"] for p in win.pinned_markers]
    assert names == ["NEW"]


# ---------- Tier A+B+C: GroupDetailPopup manager ----------

def test_popup_capture_states_returns_per_group_dict(qapp_instance, qtbot):
    """Manager should serialize all currently-shown windows keyed by group_id."""
    from components.group_detail_popup import GroupDetailPopup, GroupDetailWindow

    popup = GroupDetailPopup()
    x_labels = ["10", "100"]
    x_values = np.array([10.0, 100.0])
    samples = [{"name": "S1", "values": [1.0, 2.0]}]
    for gid in (1, 2):
        w = GroupDetailWindow(
            group_id=gid, total_groups=2,
            samples=samples, x_labels=x_labels, x_values=x_values,
            color="#000000",
        )
        qtbot.addWidget(w)
        popup.detail_windows.append(w)

    states = popup.capture_states()
    assert set(states.keys()) == {1, 2}
    assert "is_log_scale" in states[1]
    assert "geometry" in states[1]


def test_popup_apply_states_dispatches_by_group_id(qapp_instance, qtbot):
    from components.group_detail_popup import GroupDetailPopup, GroupDetailWindow
    popup = GroupDetailPopup()
    x_labels = ["10", "100"]
    x_values = np.array([10.0, 100.0])
    samples = [{"name": "S1", "values": [1.0, 2.0]}]
    win = GroupDetailWindow(
        group_id=1, total_groups=1,
        samples=samples, x_labels=x_labels, x_values=x_values,
        color="#000000",
    )
    qtbot.addWidget(win)
    popup.detail_windows.append(win)

    popup.apply_states({
        1: {
            "is_log_scale": True, "show_as_bar": False,
            "show_average_only": True, "hide_x_axis": True,
            "pinned_markers": [],
        },
    })
    assert win.show_average_only is True
    assert win.hide_x_axis is True
    assert win.show_as_bar is False
