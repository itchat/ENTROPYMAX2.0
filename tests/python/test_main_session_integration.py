"""Integration tests for main.py session save/restore wiring.

Constructing the full EntropyMaxFinal window crashes pytest under macOS due
to QWebEngineView, so we test the methods by binding them to a lightweight
stub that mimics the relevant attributes. This still exercises the real
production code (`EntropyMaxFinal._capture_session_state`, `_maybe_restore_session`,
`_restore_session`, `_on_save_and_exit`) without instantiating the heavy GUI.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture
def main_class():
    """Import the EntropyMaxFinal class without constructing it."""
    import main as main_mod
    return main_mod.EntropyMaxFinal, main_mod


@pytest.fixture
def stub_window(main_class):
    """A SimpleNamespace stub with all attributes _capture_session_state needs."""
    cls, _ = main_class
    stub = SimpleNamespace()
    stub.input_file_path = None
    stub.gps_file_path = None
    stub.selected_k_for_details = None
    stub.group_relabel_mapping = {}
    stub.group_colors = {}
    stub.selected_samples = []
    # Stub control_panel.get_analysis_parameters
    stub.control_panel = SimpleNamespace(
        get_analysis_parameters=lambda: {
            "min_groups": 2, "max_groups": 20,
            "do_permutations": True, "take_proportions": False,
            "input_file": None, "gps_file": None,
        },
        populate_parameters=lambda params: None,
        setRecentInputs=lambda entries: None,
        setRecentGps=lambda entries: None,
    )
    return stub, cls


# ---------- 6. _capture_session_state shape ----------

def test_capture_session_state_returns_all_fields(stub_window):
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    stub.selected_k_for_details = 5
    stub.group_relabel_mapping = {0: 1, 1: 2}
    stub.group_colors = {1: "#ff0000"}
    stub.selected_samples = ["S1", "S2"]

    state = cls._capture_session_state(stub)
    assert state["input_file_path"] == "/tmp/in.csv"
    assert state["gps_file_path"] == "/tmp/gps.csv"
    assert state["selected_k_for_details"] == 5
    assert state["group_relabel_mapping"] == {0: 1, 1: 2}
    assert state["group_colors"] == {1: "#ff0000"}
    assert state["selected_samples"] == ["S1", "S2"]
    assert state["analysis_params"]["min_groups"] == 2
    assert state["analysis_params"]["max_groups"] == 20
    # Should NOT contain non-serializable file paths inside analysis_params
    assert "input_file" not in state["analysis_params"]


# ---------- 7. _on_save_and_exit calls save_session ----------

def test_on_save_and_exit_calls_save_session(stub_window, monkeypatch):
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    stub.statusBar = lambda: SimpleNamespace(showMessage=lambda *a, **k: None)
    stub.close = lambda: None
    # Bind _capture_session_state as a method on the stub
    stub._capture_session_state = lambda: cls._capture_session_state(stub)

    captured = {}
    import main as main_mod
    monkeypatch.setattr(main_mod, "save_session", lambda state: captured.setdefault("state", state))

    cls._on_save_and_exit(stub)
    assert "state" in captured
    assert captured["state"]["input_file_path"] == "/tmp/in.csv"


def test_on_save_and_exit_skips_when_no_files(stub_window, monkeypatch):
    stub, cls = stub_window
    stub.statusBar = lambda: SimpleNamespace(showMessage=lambda *a, **k: None)
    stub.close = lambda: None
    stub._capture_session_state = lambda: cls._capture_session_state(stub)
    called = []
    import main as main_mod
    monkeypatch.setattr(main_mod, "save_session", lambda state: called.append(state))
    cls._on_save_and_exit(stub)
    assert called == []  # no files -> no save


# ---------- 1. maybe_restore skips when no session ----------

def test_maybe_restore_skips_when_no_session(stub_window, monkeypatch):
    stub, cls = stub_window
    import main as main_mod
    monkeypatch.setattr(main_mod, "load_session", lambda: None)
    called = []
    stub._restore_session = lambda s: called.append(s)
    cls._maybe_restore_session(stub)
    assert called == []


# ---------- 2. maybe_restore skips when files missing ----------

def test_maybe_restore_skips_when_files_missing(stub_window, monkeypatch):
    stub, cls = stub_window
    import main as main_mod
    monkeypatch.setattr(main_mod, "load_session", lambda: {
        "input_file_path": "/no/such/file.csv",
        "gps_file_path": "/no/such/gps.csv",
    })
    called = []
    stub._restore_session = lambda s: called.append(s)
    cls._maybe_restore_session(stub)
    assert called == []


# ---------- 8. file selection adds to recent list ----------

def test_capture_state_excludes_non_serializable_params(stub_window):
    """analysis_params from control_panel includes input_file/gps_file paths
    which are duplicates of top-level fields — they should be filtered out."""
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    state = cls._capture_session_state(stub)
    assert "input_file" not in state["analysis_params"]
    assert "gps_file" not in state["analysis_params"]
    assert set(state["analysis_params"].keys()) <= {
        "min_groups", "max_groups", "do_permutations", "take_proportions"
    }


# ============================================================================
# Cycle 7: Auto-K fallback after analysis
# ============================================================================

class _RestoreStub:
    """Stub mimicking EntropyMaxFinal for _restore_session tests.
    Records which methods get called by _restore_session."""

    def __init__(self):
        self.input_file_path = None
        self.gps_file_path = None
        self.selected_k_for_details = None
        self.group_relabel_mapping = {}
        self.group_colors = {}
        self.selected_samples = []
        self.current_analysis_data = {}
        self.k_called_with = []
        self.run_analysis_called_with = []

        # control panel stub
        self.control_panel = SimpleNamespace(
            input_file=None,
            gps_file=None,
            input_label=SimpleNamespace(setText=lambda *a, **k: None,
                                        setStyleSheet=lambda *a, **k: None),
            gps_label=SimpleNamespace(setText=lambda *a, **k: None,
                                      setStyleSheet=lambda *a, **k: None),
            _update_button_states=lambda: None,
            populate_parameters=lambda params: None,
            setRecentInputs=lambda entries: None,
            setRecentGps=lambda entries: None,
            get_analysis_parameters=lambda: {
                "min_groups": 2, "max_groups": 20,
                "do_permutations": True, "take_proportions": False,
                "input_file": "/tmp/in.csv", "gps_file": "/tmp/gps.csv",
            },
        )
        # map / standalone window stubs
        self.map_sample_widget = SimpleNamespace(
            sample_list=SimpleNamespace(set_selection=lambda s: None),
        )

    # Recording stubs replacing real methods
    def _on_input_file_selected(self, p):
        self.input_file_path = p

    def _on_gps_file_selected(self, p):
        self.gps_file_path = p

    def _on_run_analysis(self, params):
        self.run_analysis_called_with.append(dict(params))

    def _on_k_value_selected_and_show_details(self, k):
        self.k_called_with.append(int(k))

    def _apply_map_for_k(self, k, announce=True):
        pass

    def _on_show_group_details(self):
        pass

    def _refresh_selected_psd(self):
        pass


def _make_restore_stub_with_optimal_k(optimal_k):
    """Create a stub whose _on_run_analysis sets current_analysis_data after running."""
    stub = _RestoreStub()
    real_run = stub._on_run_analysis
    def stub_run(params):
        real_run(params)
        stub.current_analysis_data = {"optimal_k": optimal_k}
    stub._on_run_analysis = stub_run
    return stub


def test_restore_session_falls_back_to_optimal_k_when_no_saved_k(main_class, make_csv):
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _make_restore_stub_with_optimal_k(7)

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": None,
    })
    assert stub.selected_k_for_details == 7


def test_restore_session_uses_saved_k_over_optimal_k(main_class, make_csv):
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _make_restore_stub_with_optimal_k(7)

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": 4,
    })
    assert stub.selected_k_for_details == 4


def test_restore_session_skips_k_when_no_optimal_either(main_class, make_csv):
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _RestoreStub()  # current_analysis_data stays empty

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": None,
    })
    assert stub.selected_k_for_details is None


# ============================================================================
# Cycle 8: Window geometry capture/restore
# ============================================================================

class _MockWindow:
    """A mock QMainWindow-like object that records save/restore calls."""

    def __init__(self, visible=False, geometry_bytes=b"\x01\x02"):
        self._visible = visible
        self._geom = geometry_bytes
        self.show_called = False
        self.restored_with = None

    def isVisible(self):
        return self._visible

    def saveGeometry(self):
        return self._geom  # plain bytes works for our serializer

    def restoreGeometry(self, data):
        self.restored_with = bytes(data)
        return True

    def show(self):
        self.show_called = True


def test_capture_session_state_includes_window_states(stub_window):
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    stub.map_window = _MockWindow(visible=True, geometry_bytes=b"\xaa\xbb\xcc")
    stub.ch_window = _MockWindow(visible=False, geometry_bytes=b"\x11\x22")
    stub.rs_window = _MockWindow(visible=False, geometry_bytes=b"\x33\x44")
    stub.selected_psd_window = _MockWindow(visible=True, geometry_bytes=b"\xee\xff")
    stub.saveGeometry = lambda: b"\x99\x88\x77"
    # Bind helper as method on stub
    stub._capture_window_states = lambda: cls._capture_window_states(stub)

    state = cls._capture_session_state(stub)
    assert "window_states" in state
    ws = state["window_states"]
    assert ws["map_window"]["visible"] is True
    assert ws["map_window"]["geometry"] == "aabbcc"
    assert ws["ch_window"]["visible"] is False
    assert ws["selected_psd_window"]["geometry"] == "eeff"
    assert state["main_window_geometry"] == "998877"


def test_capture_session_state_handles_missing_window_attribute(stub_window):
    """Missing standalone window attrs should not crash capture."""
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    # Note: no map_window/ch_window/etc set on stub
    stub.saveGeometry = lambda: b"\x00"
    stub._capture_window_states = lambda: cls._capture_window_states(stub)
    state = cls._capture_session_state(stub)
    assert state["window_states"] == {}


def test_restore_window_states_calls_restore_and_show(main_class):
    cls, _ = main_class
    stub = SimpleNamespace()
    stub.map_window = _MockWindow(visible=False)
    stub.ch_window = _MockWindow(visible=False)
    stub.rs_window = _MockWindow(visible=False)
    stub.selected_psd_window = _MockWindow(visible=False)

    cls._restore_window_states(stub, {
        "map_window": {"visible": True, "geometry": "aabbcc"},
        "ch_window": {"visible": False, "geometry": "1122"},
    })
    assert stub.map_window.restored_with == bytes.fromhex("aabbcc")
    assert stub.map_window.show_called is True
    assert stub.ch_window.restored_with == bytes.fromhex("1122")
    assert stub.ch_window.show_called is False  # not visible


def test_restore_window_states_handles_missing_attrs(main_class):
    cls, _ = main_class
    stub = SimpleNamespace()
    # No window attributes at all
    cls._restore_window_states(stub, {
        "map_window": {"visible": True, "geometry": "aa"},
    })
    # Should not raise


def test_restore_window_states_handles_invalid_hex(main_class):
    cls, _ = main_class
    stub = SimpleNamespace()
    stub.map_window = _MockWindow(visible=False)
    cls._restore_window_states(stub, {
        "map_window": {"visible": True, "geometry": "not-valid-hex!!"},
    })
    # Should not raise; restoredWith stays None
    assert stub.map_window.restored_with is None


def test_restore_main_window_geometry_decodes_hex(main_class):
    cls, _ = main_class
    stub = SimpleNamespace()
    stub.restored = None
    stub.restoreGeometry = lambda data: setattr(stub, 'restored', bytes(data)) or True
    cls._restore_main_window_geometry(stub, "aabbcc")
    assert stub.restored == bytes.fromhex("aabbcc")


def test_restore_main_window_geometry_ignores_none(main_class):
    cls, _ = main_class
    stub = SimpleNamespace()
    stub.restoreGeometry = lambda data: (_ for _ in ()).throw(AssertionError("should not be called"))
    cls._restore_main_window_geometry(stub, None)  # no-op
    cls._restore_main_window_geometry(stub, "")  # no-op


# ============================================================================
# Group details full state capture/restore in main.py
# ============================================================================

def test_capture_session_state_includes_group_details_state(stub_window):
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    captured = {1: {"is_log_scale": True, "show_as_bar": True}}
    stub.group_detail_popup = SimpleNamespace(
        capture_states=lambda: captured,
    )
    stub.saveGeometry = lambda: b"\x00"
    stub._capture_window_states = lambda: cls._capture_window_states(stub)
    state = cls._capture_session_state(stub)
    assert "group_details_state" in state
    assert state["group_details_state"] == captured


def test_capture_session_state_handles_missing_group_detail_popup(stub_window):
    stub, cls = stub_window
    stub.input_file_path = "/tmp/in.csv"
    stub.gps_file_path = "/tmp/gps.csv"
    # No group_detail_popup attribute
    stub.saveGeometry = lambda: b"\x00"
    stub._capture_window_states = lambda: cls._capture_window_states(stub)
    state = cls._capture_session_state(stub)
    assert state["group_details_state"] == {}


def test_restore_session_applies_group_details_state(main_class, make_csv):
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _make_restore_stub_with_optimal_k(5)
    applied = []
    stub.group_detail_popup = SimpleNamespace(
        apply_states=lambda states: applied.append(states),
        capture_states=lambda: {},
    )

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": 5,
        "group_details_state": {1: {"is_log_scale": False}},
    })
    assert len(applied) == 1
    assert applied[0] == {1: {"is_log_scale": False}}


# ============================================================================
# 1:1 restore — don't auto-open group details if they weren't open at save
# ============================================================================

def test_restore_session_does_not_open_group_details_when_state_empty(main_class, make_csv):
    """If group_details_state is empty (no popups at save time), restore must
    NOT call _on_show_group_details, even when a K value is restored."""
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _make_restore_stub_with_optimal_k(5)
    show_calls = []
    stub._on_show_group_details = lambda: show_calls.append("called")
    apply_calls = []
    stub.group_detail_popup = SimpleNamespace(
        apply_states=lambda states: apply_calls.append(states),
        capture_states=lambda: {},
    )

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": 5,
        "group_details_state": {},  # empty == no popups were open
    })
    assert show_calls == []
    assert apply_calls == []
    # K value still set so map can populate
    assert stub.selected_k_for_details == 5


def test_restore_session_opens_group_details_when_state_non_empty(main_class, make_csv):
    """If group_details_state has entries, popups should reopen."""
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _make_restore_stub_with_optimal_k(5)
    show_calls = []
    stub._on_show_group_details = lambda: show_calls.append("called")
    apply_calls = []
    stub.group_detail_popup = SimpleNamespace(
        apply_states=lambda states: apply_calls.append(states),
        capture_states=lambda: {},
    )

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": 5,
        "group_details_state": {1: {"is_log_scale": True}},
    })
    assert show_calls == ["called"]
    assert apply_calls == [{1: {"is_log_scale": True}}]


def test_restore_session_does_not_reset_relabel_mapping(main_class, make_csv):
    """The K-selection step must NOT wipe the saved relabel/colors."""
    cls, _ = main_class
    in_path = make_csv("in.csv")
    gps_path = make_csv("gps.csv")
    stub = _make_restore_stub_with_optimal_k(5)
    apply_calls = []
    stub.group_detail_popup = SimpleNamespace(
        apply_states=lambda states: apply_calls.append(states),
        capture_states=lambda: {},
    )

    cls._restore_session(stub, {
        "input_file_path": in_path,
        "gps_file_path": gps_path,
        "selected_k_for_details": 5,
        "group_relabel_mapping": {"0": 1, "1": 2},
        "group_colors": {"1": "#ff0000"},
        "group_details_state": {},
    })
    assert stub.group_relabel_mapping == {0: 1, 1: 2}
    assert stub.group_colors == {1: "#ff0000"}
