"""
Selected PSD widget
Displays PSD curves (grain size vs %) for the currently selected samples on one plot.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal
from .visualization_settings import VisualizationSettings


class SelectedPSDWidget(QWidget):
    """Overlay PSD curves for selected samples on a single chart.
    Includes Group Details-like options: log/linear toggle, bar/line toggle,
    hover highlight with tooltip, click to pin markers, clear markers.
    """

    # Muted color palette for comfortable viewing (ColorBrewer-inspired)
    PALETTE = [
        (55, 126, 184),   # steel blue
        (228, 26, 28),    # muted red
        (77, 175, 74),    # sage green
        (152, 78, 163),   # soft purple
        (255, 127, 0),    # warm orange
        (166, 86, 40),    # brown
        (247, 129, 191),  # pink
        (153, 153, 153),  # grey
        (0, 139, 139),    # teal
        (205, 133, 63),   # peru
        (106, 90, 205),   # slate blue
        (60, 179, 113),   # medium sea green
    ]

    # Emitted when a sample line/bar is clicked
    lineClicked = Signal(str)  # sample_name
    sampleHovered = Signal(str)  # emitted on hover over a sample curve
    sampleUnhovered = Signal()  # emitted when hover leaves

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = VisualizationSettings()
        self._is_log_scale = True  # default to log scale (like Group Details)
        self._show_as_bar = False  # default to line chart

        # overlays and state
        self.point_marker = None
        self.coord_label = None
        self.pinned_markers = []
        self.plot_items = []  # per-sample render info for hover/click

        self._setup_ui()
        self.settings.settingsChanged.connect(self._on_settings_changed)

        # data cache for replot
        self._last_x_labels = None
        self._last_samples = None  # list of dicts: {name, values}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Plot only; actions will be injected into the window toolbar via augment_toolbar()
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self._apply_styling()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
        # Create legend (top-right)
        self.legend = self.plot_widget.addLegend(offset=(10, 10))
        layout.addWidget(self.plot_widget)

        # Connect scene events for hover/click interactions
        scene = self.plot_widget.scene()
        scene.sigMouseMoved.connect(self._on_mouse_hover)
        scene.sigMouseClicked.connect(self._on_plot_clicked)

    def augment_toolbar(self, toolbar):
        """Add module-specific actions to a parent toolbar (StandaloneWindow)."""
        # Initialize actions if not present
        self.scale_action = getattr(self, 'scale_action', QAction("Switch to Linear" if self._is_log_scale else "Switch to Log", self))
        self.scale_action.setText("Switch to Linear" if self._is_log_scale else "Switch to Log")
        self.scale_action.setToolTip("Toggle between logarithmic and linear scale")
        self.scale_action.triggered.connect(self._toggle_scale)
        toolbar.addAction(self.scale_action)

        self.chart_type_action = getattr(self, 'chart_type_action', QAction("Switch to Bar" if not self._show_as_bar else "Switch to Line", self))
        self.chart_type_action.setText("Switch to Bar" if not self._show_as_bar else "Switch to Line")
        self.chart_type_action.setToolTip("Toggle between line and bar chart")
        self.chart_type_action.triggered.connect(self._toggle_chart_type)
        toolbar.addAction(self.chart_type_action)

        self.clear_points_action = getattr(self, 'clear_points_action', QAction("Clear Markers", self))
        self.clear_points_action.setToolTip("Remove all pinned markers and hide hover label")
        self.clear_points_action.triggered.connect(self._clear_all_points)
        toolbar.addAction(self.clear_points_action)

    def _on_settings_changed(self):
        # Apply axis/tick styles and replot to reflect line thickness changes
        self._apply_styling()
        self._replot_last()

    def _apply_styling(self):
        axis_style = self.settings.get_axis_style()
        tick_style = self.settings.get_tick_style()
        self.plot_widget.setLabel('left', 'Frequency', units='%', **axis_style)
        self.plot_widget.setLabel('bottom', 'Grain Size', units='μm', unitPrefix='', **axis_style)
        left_axis = self.plot_widget.getAxis('left')
        bottom_axis = self.plot_widget.getAxis('bottom')
        tick_pen = pg.mkPen(color=tick_style['color'])
        left_axis.setPen(tick_pen)
        bottom_axis.setPen(tick_pen)
        left_axis.setTextPen(tick_style['color'])
        bottom_axis.setTextPen(tick_style['color'])
        from PyQt6.QtGui import QFont
        tick_font = QFont()
        tick_font.setPointSize(self.settings.tick_font_size)
        left_axis.setTickFont(tick_font)
        bottom_axis.setTickFont(tick_font)

    @staticmethod
    def _parse_grain_sizes(labels):
        """Convert string labels like '0.1 μm' or '10' to numeric floats (μm)."""
        values = []
        for label in labels or []:
            try:
                s = str(label).replace('μm', '').replace('um', '').strip()
                values.append(float(s))
            except Exception:
                # fallback to sequential index if unparsable
                values.append(len(values) + 1)
        return np.array(values, dtype=float)

    def clear(self):
        self.plot_widget.clear()
        # re-add legend after clear
        self.legend = self.plot_widget.addLegend(offset=(10, 10))
        self._last_x_labels = None
        self._last_samples = None
        self._clear_all_points()
        self.plot_items = []

    def update_curves(self, x_labels, samples):
        """Update plot with new sample curves.

        Args:
            x_labels: list[str] of grain size labels
            samples: list[dict] with keys {'name': str, 'values': list[float]}
        """
        self._last_x_labels = list(x_labels) if x_labels else None
        self._last_samples = list(samples) if samples else None

        self.plot_widget.clear()
        self.legend = self.plot_widget.addLegend(offset=(10, 10))
        self.plot_items = []
        self._clear_hover_overlays()
        self._clear_pinned_points()

        if not x_labels or not samples:
            return

        x_numeric = self._parse_grain_sizes(x_labels)
        if len(x_numeric) == 0:
            return

        # Transform x for plotting when log scale
        if self._is_log_scale:
            # Avoid log(<=0)
            x_plot = np.where(x_numeric > 0, np.log10(x_numeric.astype(float)), np.nan)
            valid_mask = ~np.isnan(x_plot)
        else:
            x_plot = x_numeric.astype(float)
            valid_mask = np.isfinite(x_plot)

        if self._show_as_bar:
            # Bar chart rendering with hover/click support
            for i, sample in enumerate(samples):
                name = sample.get('name', f'Sample {i+1}')
                y = np.array(sample.get('values') or [], dtype=float)
                n = min(len(y), len(x_plot))
                if n == 0:
                    continue
                xs = x_plot[:n]
                ys = y[:n]
                mask = valid_mask[:n]
                xs = xs[mask]
                ys = ys[mask]
                if len(xs) == 0:
                    continue

                base_w = self._compute_bar_widths(xs)
                w = base_w * float(self.settings.bar_width_scale)
                # per-sample color from muted palette
                r, g, b = self.PALETTE[i % len(self.PALETTE)]
                brush_default = pg.mkBrush(r, g, b, 160)
                brush_hover = pg.mkBrush(r, g, b, 230)
                pen_bar = pg.mkPen(r, g, b, width=1)

                bar_item = pg.BarGraphItem(x=xs, height=ys, width=w, brush=brush_default, pen=pen_bar)
                self.plot_widget.addItem(bar_item)

                # Invisible line for interaction and hover highlighting
                line_pen = pg.mkPen(color=(0, 0, 0, 0), width=0.001)
                plot_item = self.plot_widget.plot(xs, ys, pen=line_pen, name=name)

                hover_width = self.settings.line_thickness + 1.5
                click_width = self.settings.line_thickness + 1.0
                self.plot_items.append({
                    'plot_item': plot_item,
                    'bar_item': bar_item,
                    'sample_name': name,
                    'original_pen': line_pen,
                    'hover_pen': pg.mkPen(color=(r, g, b, 255), width=hover_width),
                    'click_pen': pg.mkPen(color=(180, 120, 40, 255), width=click_width),
                    'default_brush': brush_default,
                    'hover_brush': brush_hover,
                    'default_bar_pen': pen_bar,
                    'bar_x': xs,
                    'bar_w': w,
                    'bar_h': ys,
                    'y0': 0.0
                })
        else:
            # Line chart rendering
            for i, sample in enumerate(samples):
                name = sample.get('name', f'Sample {i+1}')
                y = np.array(sample.get('values') or [], dtype=float)
                n = min(len(y), len(x_plot))
                if n == 0:
                    continue
                xs = x_plot[:n]
                ys = y[:n]
                mask = valid_mask[:n]
                xs = xs[mask]
                ys = ys[mask]
                if len(xs) == 0:
                    continue

                r, g, b = self.PALETTE[i % len(self.PALETTE)]
                pen = pg.mkPen(color=(r, g, b), width=self.settings.line_thickness)
                plot_item = self.plot_widget.plot(xs, ys, pen=pen, name=name)

                hover_width = self.settings.line_thickness + 1.5
                click_width = self.settings.line_thickness + 1.0
                self.plot_items.append({
                    'plot_item': plot_item,
                    'sample_name': name,
                    'original_pen': pen,
                    'hover_pen': pg.mkPen(color=(r, g, b), width=hover_width),
                    'click_pen': pg.mkPen(color=(180, 120, 40, 255), width=click_width)
                })

        # Update x ticks
        if self._is_log_scale:
            self._update_log_ticks(x_numeric)
        else:
            self._update_linear_ticks(x_numeric)

    def _replot_last(self):
        if self._last_x_labels is not None and self._last_samples is not None:
            self.update_curves(self._last_x_labels, self._last_samples)

    def reset_to_defaults(self):
        """Reset local view toggles and clear markers; keep current data.
        Uses the public setters to ensure state, labels, and replot stay in sync.
        """
        self._clear_all_points()
        # Ensure default: Log scale ON, Line chart
        self.set_log_scale(True)
        self.set_chart_type_bar(False)
        # Reset view range
        try:
            self.plot_widget.autoRange()
        except Exception:
            pass

    def set_log_scale(self, enabled: bool):
        self._is_log_scale = bool(enabled)
        if hasattr(self, 'scale_action'):
            self.scale_action.setText("Switch to Linear" if self._is_log_scale else "Switch to Log")
        self._replot_last()
        # Linear axis must start at 0
        if not self._is_log_scale and self._last_x_labels:
            x_vals = self._parse_grain_sizes(self._last_x_labels)
            if len(x_vals) > 0:
                self.plot_widget.setXRange(0, float(np.max(x_vals)) * 1.05, padding=0)

    def set_chart_type_bar(self, enabled: bool):
        self._show_as_bar = bool(enabled)
        if hasattr(self, 'chart_type_action'):
            self.chart_type_action.setText("Switch to Line" if self._show_as_bar else "Switch to Bar")
        self._replot_last()

    def _toggle_scale(self):
        self.set_log_scale(not self._is_log_scale)

    def _toggle_chart_type(self):
        self.set_chart_type_bar(not self._show_as_bar)

    def _update_log_ticks(self, x_numeric):
        ax = self.plot_widget.getAxis('bottom')
        major, minor = [], []
        finite = x_numeric[np.isfinite(x_numeric) & (x_numeric > 0)]
        if finite.size == 0:
            ax.setTicks([[]])
            return
        mn, mx = float(np.min(finite)), float(np.max(finite))
        import math
        log_min = math.floor(np.log10(mn))
        log_max = math.ceil(np.log10(mx))
        for exp in range(int(log_min), int(log_max) + 1):
            val = 10 ** exp
            if mn <= val <= mx:
                pos = np.log10(val)
                label = f"{val:.0f}" if val >= 1 else f"{val:.2f}"
                major.append((pos, label))
            for mult in range(2, 10):
                mval = mult * (10 ** exp)
                if mn <= mval <= mx:
                    minor.append((np.log10(mval), ''))
        ax.setTicks([major, minor])

    def _update_linear_ticks(self, x_numeric):
        ax = self.plot_widget.getAxis('bottom')
        finite = x_numeric[np.isfinite(x_numeric)]
        if finite.size == 0:
            ax.setTicks([[]])
            return
        vmin, vmax = float(np.min(finite)), float(np.max(finite))
        if vmax <= vmin:
            ax.setTicks([[]])
            return
        span = vmax - vmin
        step = 10 ** int(np.floor(np.log10(span / 7)))
        vals = np.arange(np.floor(vmin / step) * step, np.ceil(vmax / step) * step + 0.5 * step, step)
        major = [(float(v), f"{v:.0f}" if v >= 1 else f"{v:.2f}") for v in vals if vmin <= v <= vmax]
        # Minor ticks: subdivide major intervals into 5
        minor = []
        if len(major) >= 2:
            mstep = (major[1][0] - major[0][0]) / 5
            x = major[0][0] - (major[1][0] - major[0][0])
            while x <= major[-1][0] + (major[1][0] - major[0][0]):
                if vmin <= x <= vmax and not any(abs(x - m[0]) < mstep * 0.1 for m in major):
                    minor.append((x, ''))
                x += mstep
        ax.setTicks([major, minor])

    # ===== Interaction & overlay helpers =====
    def _ensure_hover_items(self):
        if self.point_marker is None:
            self.point_marker = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(180, 80, 60, 180), pen=pg.mkPen(None))
            self.plot_widget.addItem(self.point_marker)
        if self.coord_label is None:
            self.coord_label = pg.TextItem(color=(20, 20, 20))
            self.coord_label.setAnchor((0, 1))
            self.plot_widget.addItem(self.coord_label)

    def _clear_hover_overlays(self):
        if self.point_marker is not None:
            self.point_marker.setData([], [])
        if self.coord_label is not None:
            self.coord_label.setText("")

    def _find_existing_marker(self, x_plot, y_plot, sample_name):
        for i, marker in enumerate(self.pinned_markers):
            if marker.get('sample_name') == sample_name:
                if abs(marker['x_plot'] - x_plot) < 1e-4 and abs(marker['y_plot'] - y_plot) < 1e-4:
                    return i
        return -1

    def _remove_pinned_marker(self, index):
        marker = self.pinned_markers.pop(index)
        try:
            self.plot_widget.removeItem(marker['scatter'])
            self.plot_widget.removeItem(marker['label'])
        except Exception:
            pass

    def _pin_point(self, x_plot, y_plot, x_disp, y_disp, sample_name: str):
        import time
        existing = self._find_existing_marker(x_plot, y_plot, sample_name)
        if existing >= 0:
            self._remove_pinned_marker(existing)
            self._just_unpinned = time.time()
            return False

        scatter = pg.ScatterPlotItem(size=7, brush=pg.mkBrush(70, 90, 110, 200), pen=pg.mkPen(50, 70, 90), symbol='o')
        scatter.setData([x_plot], [y_plot])
        label = pg.TextItem(color=(50, 70, 90))
        label.setAnchor((0, 1))
        x_txt = self._format_number(x_disp)
        y_txt = self._format_number(y_disp)
        label.setText(f"{x_txt} μm, {y_txt} % — {sample_name}")
        label.setPos(x_plot, y_plot)
        self.plot_widget.addItem(scatter)
        self.plot_widget.addItem(label)
        self.pinned_markers.append({
            'scatter': scatter, 'label': label,
            'sample_name': sample_name, 'x_plot': x_plot, 'y_plot': y_plot
        })
        return True

    def _clear_pinned_points(self):
        if not self.pinned_markers:
            return
        for it in self.pinned_markers:
            try:
                self.plot_widget.removeItem(it['scatter'])
                self.plot_widget.removeItem(it['label'])
            except Exception:
                pass
        self.pinned_markers = []

    def _clear_all_points(self):
        self._clear_pinned_points()
        self._clear_hover_overlays()

    def _format_number(self, v: float) -> str:
        if v is None:
            return ""
        if abs(v) >= 100:
            return f"{v:.0f}"
        if abs(v) >= 1:
            return f"{v:.1f}"
        if abs(v) >= 0.1:
            return f"{v:.2f}"
        return f"{v:.3f}"

    def _compute_bar_widths(self, x_positions: np.ndarray) -> np.ndarray:
        if x_positions is None or len(x_positions) == 0:
            return np.array([])
        if len(x_positions) == 1:
            return np.array([0.8])
        widths = np.zeros_like(x_positions, dtype=float)
        n = len(x_positions)
        for i in range(n):
            if i == 0:
                left_gap = x_positions[1] - x_positions[0]
                right_gap = x_positions[1] - x_positions[0]
            elif i == n - 1:
                left_gap = x_positions[-1] - x_positions[-2]
                right_gap = x_positions[-1] - x_positions[-2]
            else:
                left_gap = x_positions[i] - x_positions[i-1]
                right_gap = x_positions[i+1] - x_positions[i]
            gap = max(0.0, min(left_gap, right_gap))
            widths[i] = 0.8 * gap if gap > 0 else 0.6
        return widths

    # ===== Hover emit and external highlight =====
    def _emit_hover(self, sample_name):
        if not hasattr(self, '_last_hover_sample'):
            self._last_hover_sample = None
        if sample_name == self._last_hover_sample:
            return
        self._last_hover_sample = sample_name
        if sample_name:
            self.sampleHovered.emit(sample_name)
        else:
            self.sampleUnhovered.emit()

    def highlight_sample_externally(self, sample_name):
        self._external_highlight = sample_name
        for item_data in self.plot_items:
            if item_data['sample_name'] == sample_name:
                item_data['plot_item'].setPen(item_data['hover_pen'])
                if 'bar_item' in item_data:
                    item_data['bar_item'].setOpts(brush=item_data.get('hover_brush'))
            else:
                item_data['plot_item'].setPen(item_data['original_pen'])
                if 'bar_item' in item_data:
                    item_data['bar_item'].setOpts(
                        brush=item_data.get('default_brush'),
                        pen=item_data.get('default_bar_pen')
                    )

    def unhighlight_externally(self):
        self._external_highlight = None
        for item_data in self.plot_items:
            item_data['plot_item'].setPen(item_data['original_pen'])
            if 'bar_item' in item_data:
                item_data['bar_item'].setOpts(
                    brush=item_data.get('default_brush'),
                    pen=item_data.get('default_bar_pen')
                )

    # ===== Hover and click handling =====
    def _on_plot_clicked(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._clear_pinned_points()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Scene -> data coords
        pos = event.scenePos()
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        x_click = mouse_point.x()
        y_click = mouse_point.y()

        # If bar mode, rectangle hit-test first
        if self._show_as_bar:
            for item_data in self.plot_items:
                if 'bar_item' not in item_data:
                    continue
                xs = item_data.get('bar_x')
                ws = item_data.get('bar_w')
                hs = item_data.get('bar_h')
                y0 = float(item_data.get('y0', 0.0))
                if xs is None or ws is None or hs is None:
                    continue
                for idx in range(len(xs)):
                    x_left = float(xs[idx]) - float(ws[idx]) / 2.0
                    x_right = float(xs[idx]) + float(ws[idx]) / 2.0
                    y_bottom = y0
                    y_top = float(y0 + hs[idx])
                    if (x_left <= x_click <= x_right) and (min(y_bottom, y_top) <= y_click <= max(y_bottom, y_top)):
                        x_plot = float(xs[idx])
                        y_plot = float(y_top)
                        x_disp = 10 ** x_plot if self._is_log_scale else float(xs[idx])
                        y_disp = float(y_top)
                        plot_item = item_data['plot_item']
                        click_pen = item_data['click_pen']
                        original_pen = item_data['original_pen']
                        plot_item.setPen(click_pen)
                        original_bar_pen = item_data.get('default_bar_pen')
                        item_data['bar_item'].setOpts(pen=pg.mkPen(180, 120, 40, 255))
                        def reset_color():
                            plot_item.setPen(original_pen)
                            item_data['bar_item'].setOpts(pen=original_bar_pen)
                        QTimer.singleShot(200, reset_color)
                        pinned = self._pin_point(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
                        if pinned:
                            try:
                                self.lineClicked.emit(item_data['sample_name'])
                            except Exception:
                                pass
                        return

        # Fallback: nearest curve point
        min_distance = float('inf')
        closest = None  # (item_data, min_idx)
        for item_data in self.plot_items:
            plot_item = item_data['plot_item']
            x_data, y_data = plot_item.getData()
            if len(x_data) == 0:
                continue
            x_range = self.plot_widget.viewRange()[0]
            y_range = self.plot_widget.viewRange()[1]
            x_scale = x_range[1] - x_range[0] if x_range[1] != x_range[0] else 1
            y_scale = y_range[1] - y_range[0] if y_range[1] != y_range[0] else 1
            distances = np.sqrt(((x_data - x_click)/x_scale)**2 + ((y_data - y_click)/y_scale)**2)
            min_idx = int(np.argmin(distances))
            if distances[min_idx] < min_distance:
                min_distance = distances[min_idx]
                closest = (item_data, min_idx)
        if closest and min_distance < 0.08:
            item_data, idx = closest
            plot_item = item_data['plot_item']
            x_data, y_data = plot_item.getData()
            x_plot = float(x_data[idx])
            y_plot = float(y_data[idx])
            x_disp = 10 ** x_plot if self._is_log_scale else float(x_plot)
            y_disp = float(y_plot)
            click_pen = item_data['click_pen']
            original_pen = item_data['original_pen']
            plot_item.setPen(click_pen)
            def reset_color():
                plot_item.setPen(original_pen)
            QTimer.singleShot(200, reset_color)
            pinned = self._pin_point(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
            if pinned:
                try:
                    self.lineClicked.emit(item_data['sample_name'])
                except Exception:
                    pass

    def _on_mouse_hover(self, pos):
        import time
        # Skip hover briefly after unpinning to avoid re-flash
        if hasattr(self, '_just_unpinned') and time.time() - self._just_unpinned < 0.3:
            self._clear_hover_overlays()
            self._emit_hover(None)
            return

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        x_hover = mouse_point.x()
        y_hover = mouse_point.y()

        x_range = self.plot_widget.viewRange()[0]
        y_range = self.plot_widget.viewRange()[1]
        x_scale = x_range[1] - x_range[0] if x_range[1] != x_range[0] else 1
        y_scale = y_range[1] - y_range[0] if y_range[1] != y_range[0] else 1

        min_distance = float('inf')
        closest = None

        # Reset pens and bar brushes
        for item_data in self.plot_items:
            item_data['plot_item'].setPen(item_data['original_pen'])
            if 'bar_item' in item_data:
                item_data['bar_item'].setOpts(brush=item_data.get('default_brush'), pen=item_data.get('default_bar_pen'))

        # Bar hover rect test first
        if self._show_as_bar:
            for item_data in self.plot_items:
                if 'bar_item' not in item_data:
                    continue
                xs = item_data.get('bar_x')
                ws = item_data.get('bar_w')
                hs = item_data.get('bar_h')
                y0 = float(item_data.get('y0', 0.0))
                if xs is None or ws is None or hs is None:
                    continue
                for idx in range(len(xs)):
                    x_left = float(xs[idx]) - float(ws[idx]) / 2.0
                    x_right = float(xs[idx]) + float(ws[idx]) / 2.0
                    y_bottom = y0
                    y_top = float(y0 + hs[idx])
                    if (x_left <= x_hover <= x_right) and (min(y_bottom, y_top) <= y_hover <= max(y_bottom, y_top)):
                        plot_item = item_data['plot_item']
                        plot_item.setPen(item_data['hover_pen'])
                        item_data['bar_item'].setOpts(brush=item_data.get('hover_brush'))
                        x_plot = float(xs[idx])
                        y_plot = float(y_top)
                        x_disp = 10 ** x_plot if self._is_log_scale else float(xs[idx])
                        y_disp = float(y_top)
                        self._update_hover_display(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
                        self._emit_hover(item_data['sample_name'])
                        return

        # Otherwise compute nearest point
        for item_data in self.plot_items:
            plot_item = item_data['plot_item']
            x_data, y_data = plot_item.getData()
            if len(x_data) == 0:
                continue
            distances = np.sqrt(((x_data - x_hover)/x_scale)**2 + ((y_data - y_hover)/y_scale)**2)
            min_idx = int(np.argmin(distances))
            if distances[min_idx] < min_distance:
                min_distance = distances[min_idx]
                closest = (item_data, min_idx)
        if closest and min_distance < 0.06:
            item_data, idx = closest
            plot_item = item_data['plot_item']
            x_data, y_data = plot_item.getData()
            x_plot = float(x_data[idx])
            y_plot = float(y_data[idx])
            plot_item.setPen(item_data['hover_pen'])
            x_disp = 10 ** x_plot if self._is_log_scale else float(x_plot)
            y_disp = float(y_plot)
            self._update_hover_display(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
            self._emit_hover(item_data['sample_name'])
        else:
            self._clear_hover_overlays()
            self._emit_hover(None)
        
    def _update_hover_display(self, x_plot, y_plot, x_disp, y_disp, sample_name: str):
        self._ensure_hover_items()
        self.point_marker.setData([x_plot], [y_plot])
        x_txt = self._format_number(x_disp)
        y_txt = self._format_number(y_disp)
        self.coord_label.setText(f"{x_txt} μm, {y_txt} % — {sample_name}")
        self.coord_label.setPos(x_plot, y_plot)
        
