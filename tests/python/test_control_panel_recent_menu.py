"""pytest-qt tests for the recent files dropdown UI in ControlPanel."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists once
@pytest.fixture(scope="session")
def qapp_instance():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def control_panel(qapp_instance, qtbot):
    from components.control_panel import ControlPanel
    cp = ControlPanel()
    qtbot.addWidget(cp)
    return cp


def _entry(name: str, path: str = None) -> dict:
    return {
        "name": name,
        "path": path or f"/tmp/{name}",
        "last_used": "2026-04-08T12:00:00",
    }


# ---------- 1. setRecentInputs populates menu ----------

def test_set_recent_inputs_populates_menu(control_panel):
    entries = [_entry("a.csv"), _entry("b.csv")]
    control_panel.setRecentInputs(entries)
    menu = control_panel.recent_input_btn.menu()
    actions = [a for a in menu.actions() if a.isEnabled()]
    assert len(actions) == 2
    assert actions[0].text() == "a.csv"
    assert actions[1].text() == "b.csv"
    assert actions[0].toolTip() == "/tmp/a.csv"


# ---------- 2. empty list shows disabled placeholder ----------

def test_set_recent_inputs_empty_shows_disabled_placeholder(control_panel):
    control_panel.setRecentInputs([])
    menu = control_panel.recent_input_btn.menu()
    actions = list(menu.actions())
    assert len(actions) == 1
    assert not actions[0].isEnabled()


# ---------- 3. trigger emits inputFileSelected ----------

def test_triggering_recent_input_emits_input_file_selected(control_panel, qtbot):
    control_panel.setRecentInputs([_entry("a.csv", "/tmp/a.csv")])
    menu = control_panel.recent_input_btn.menu()
    action = menu.actions()[0]
    with qtbot.waitSignal(control_panel.inputFileSelected, timeout=1000) as blocker:
        action.trigger()
    assert blocker.args == ["/tmp/a.csv"]


# ---------- 4. trigger gps emits gpsFileSelected ----------

def test_triggering_recent_gps_emits_gps_file_selected(control_panel, qtbot):
    control_panel.setRecentGps([_entry("g.csv", "/tmp/g.csv")])
    menu = control_panel.recent_gps_btn.menu()
    action = menu.actions()[0]
    with qtbot.waitSignal(control_panel.gpsFileSelected, timeout=1000) as blocker:
        action.trigger()
    assert blocker.args == ["/tmp/g.csv"]


# ---------- 5. triggering recent input updates label ----------

def test_triggering_recent_input_updates_label(control_panel):
    control_panel.setRecentInputs([_entry("hello.csv", "/tmp/hello.csv")])
    control_panel.recent_input_btn.menu().actions()[0].trigger()
    assert "hello.csv" in control_panel.input_label.text()


# ---------- 6. populate_parameters roundtrip ----------

def test_populate_parameters_roundtrip(control_panel):
    params = {
        "min_groups": 3,
        "max_groups": 12,
        "do_permutations": False,
        "take_proportions": True,
    }
    control_panel.populate_parameters(params)
    out = control_panel.get_analysis_parameters()
    assert out["min_groups"] == 3
    assert out["max_groups"] == 12
    assert out["do_permutations"] is False
    assert out["take_proportions"] is True


# ---------- 7. populate_parameters ignores unknown keys ----------

def test_populate_parameters_ignores_unknown_keys(control_panel):
    control_panel.populate_parameters({"unknown_key": 99, "min_groups": 4})
    out = control_panel.get_analysis_parameters()
    assert out["min_groups"] == 4
