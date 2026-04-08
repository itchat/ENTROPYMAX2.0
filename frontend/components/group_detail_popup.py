"""
Group detail popup component for displaying line charts for each group.
"""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMainWindow, QToolBar, QFileDialog, QApplication, QFrame
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QObject, QTimer
from PyQt6.QtGui import QAction
from .visualization_settings import VisualizationSettings
from .settings_dialog import SettingsDialog


class GroupDetailPopup(QObject):
    """Manager class for creating and managing group detail popup windows."""

    # Signal emitted when a sample line is clicked in any group detail window
    sampleLineClicked = Signal(str)  # sample_name
    sampleHovered = Signal(str)  # emitted when hovering a sample in any PSD window
    sampleUnhovered = Signal()  # emitted when hover leaves

    def __init__(self, main_window=None):
        super().__init__()
        self.detail_windows = []
        self.data_path = None
        self.group_data = {}
        self.main_window = main_window
        
    
    def _parse_grain_sizes(self, labels):
        """
        Parse grain size labels to numeric values.
        Assumes grain sizes are numeric values (e.g., '0.1', '1', '10', '100')
        
        Args:
            labels: List of grain size labels
        
        Returns:
            NumPy array of numeric grain sizes
        """
        numeric_values = []
        for label in labels:
            try:
                # Remove unit if present and convert to float
                value_str = label.replace('μm', '').replace('um', '').strip()
                numeric_values.append(float(value_str))
            except (ValueError, AttributeError):
                # If can't parse, use index as fallback
                numeric_values.append(len(numeric_values) + 1)
        
        return np.array(numeric_values)
    
    def _create_popup_windows(self, grouped_samples, total_groups, x_unit='μm', y_unit='a.u.', group_colors=None):
        """
        Create popup windows for each group showing line charts.

        Args:
            grouped_samples: Dictionary with group data
            total_groups: Total number of groups (K)
            x_unit: Unit label for x-axis
            y_unit: Unit label for y-axis
            group_colors: Optional dict {group_number: hex_color}. If None, uses brown-yellow gradient.
        """
        if group_colors is None:
            base_colors = ['#2196F3', '#4CAF50', '#FF9800', '#F44336', '#9C27B0',
                          '#00BCD4', '#8BC34A', '#FFC107', '#E91E63', '#673AB7']
            group_colors = None  # use base_colors fallback below

        for group_idx, (group_id, samples) in enumerate(sorted(grouped_samples.items())):
            if not samples:
                continue

            # Use provided group_colors dict, or fall back to base_colors list
            if group_colors is not None:
                color = group_colors.get(group_id, '#888888')
            else:
                color = base_colors[group_idx % len(base_colors)]

            # Create window for this group
            window = GroupDetailWindow(
                group_id=group_id,
                total_groups=int(total_groups),
                samples=samples,
                x_labels=self.x_labels,
                x_values=self.x_values,
                color=color,
                x_unit=x_unit,
                y_unit=y_unit,
                manager=self  # Pass manager reference for layout sync
            )
            
            # Don't set geometry yet - will be done by tiling
            
            # Connect signals from each window
            window.lineClicked.connect(self.sampleLineClicked)
            window.sampleHovered.connect(self.sampleHovered)
            window.sampleUnhovered.connect(self.sampleUnhovered)

            window.show()
            self.detail_windows.append(window)
        
        # After all windows created, tile them automatically
        self._tile_windows_vertically()
    
    def load_and_show_popups_from_data(self, group_details, k_value, x_unit='μm', y_unit='a.u.', group_colors=None):
        """
        Load and show popups from extracted group details data.
        
        Args:
            group_details: Dictionary from DataPipeline.extract_group_details()
            k_value: Number of groups
            x_unit: Unit label for x-axis
            y_unit: Unit label for y-axis
        """
        # Close any existing windows
        self.close_all()
        
        # Convert group_details to grouped_samples format
        grouped_samples = {}
        for group_id, details in group_details.items():
            grouped_samples[group_id] = details['samples']
            self.x_labels = details['x_labels']
            self.x_values = self._parse_grain_sizes(details['x_labels'])
            
            # Debug: Check lengths
            print(f"DEBUG Group {group_id}: x_labels={len(self.x_labels)}, x_values={len(self.x_values)}")
            if details['samples']:
                print(f"DEBUG Group {group_id}: first sample values length={len(details['samples'][0]['values'])}")
        
        # Create popup windows
        self._create_popup_windows(grouped_samples, total_groups=int(k_value), x_unit=x_unit, y_unit=y_unit, group_colors=group_colors)
    
    def _tile_windows_vertically(self):
        """Tile windows in 2+2 overlapping column layout (up to 20 groups).

        Layout:
          Col 1: groups 1-5  (left)    Col 2: groups 6-10  (right)
          Col 3: groups 11-15 (overlay col 1, offset +30x +25y)
          Col 4: groups 16-20 (overlay col 2, offset +30x +25y)
        """
        if not self.detail_windows:
            return

        # Use the screen where the main window is, not just primary
        screen = None
        if self.main_window is not None:
            screen = self.main_window.screen()
        if screen is None:
            screen = QApplication.primaryScreen()

        avail = screen.availableGeometry()
        sx, sy = avail.x(), avail.y()
        sw, sh = avail.width(), avail.height()

        top_margin, bottom_margin, side_margin = 40, 20, 20
        spacing, col_spacing = 6, 10
        overlay_dx, overlay_dy = 30, 25

        avail_h = sh - top_margin - bottom_margin
        base_col_w = (sw - 2 * side_margin - col_spacing) // 2

        # Split windows into columns of up to 5
        columns = []
        for i in range(0, len(self.detail_windows), 5):
            columns.append(self.detail_windows[i:i + 5])

        for ci, col_wins in enumerate(columns):
            count = len(col_wins)
            is_right = (ci % 2) == 1
            is_overlay = ci >= 2

            base_x = sx + side_margin + (base_col_w + col_spacing if is_right else 0)

            if is_overlay:
                x = base_x + overlay_dx
                y_start = sy + top_margin + overlay_dy
                col_w = base_col_w - overlay_dx
                col_h = avail_h - overlay_dy
            else:
                x = base_x
                y_start = sy + top_margin
                col_w = base_col_w
                col_h = avail_h

            win_h = max(150, (col_h - (count - 1) * spacing) // count)

            for j, window in enumerate(col_wins):
                y = y_start + j * (win_h + spacing)
                window.setGeometry(int(x), int(y), int(col_w), int(win_h))
    
    def apply_layout_to_all(self, source_settings):
        """Apply layout settings from one window to all windows.

        Syncs chart type, scale, average-only, view range, and window size.
        """
        for window in self.detail_windows:
            window.apply_layout_settings(source_settings)
    
    def close_all(self):
        """Close all open detail windows."""
        for window in self.detail_windows:
            window.close()
        self.detail_windows.clear()

    def capture_states(self) -> dict:
        """Return {group_id: full_state} for all currently-open detail windows."""
        out = {}
        for win in self.detail_windows:
            try:
                gid = int(win.group_id)
                out[gid] = win.get_full_state()
            except Exception:
                pass
        return out

    def apply_states(self, states_by_gid: dict) -> None:
        """Apply per-group full state to currently-open detail windows."""
        if not states_by_gid:
            return
        # Coerce keys to int (JSON returns string keys)
        normalized = {}
        for k, v in states_by_gid.items():
            try:
                normalized[int(k)] = v
            except (ValueError, TypeError):
                pass
        for win in self.detail_windows:
            try:
                gid = int(win.group_id)
            except Exception:
                continue
            state = normalized.get(gid)
            if state is not None:
                try:
                    win.apply_full_state(state)
                except Exception:
                    pass

    def highlight_sample(self, sample_name):
        """Highlight a sample across all group detail windows (from map hover)."""
        for window in self.detail_windows:
            window.highlight_sample_externally(sample_name)

    def unhighlight_all(self):
        """Clear all external highlights across all windows."""
        for window in self.detail_windows:
            window.unhighlight_externally()


class GroupDetailWindow(QMainWindow):
    """Individual popup window showing line chart for a specific group."""

    # Signal emitted when a line is clicked
    lineClicked = Signal(str)  # sample_name
    sampleHovered = Signal(str)  # emitted on hover over a sample curve
    sampleUnhovered = Signal()  # emitted when hover leaves

    def __init__(self, group_id, total_groups, samples, x_labels, x_values, color, x_unit='\u03bcm', y_unit='a.u.', manager=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window)
        self.group_id = int(group_id)
        self.total_groups = int(total_groups)
        self.samples = samples
        self.x_labels = x_labels
        self.x_values = x_values
        self.base_color = color
        self.x_unit = x_unit
        self.y_unit = y_unit
        self.manager = manager  # Reference to GroupDetailPopup for layout sync
        self.plot_items = []  # plot items and meta per sample
        self.is_log_scale = True  # default to logarithmic x
        self.show_as_bar = True  # default to bar chart per request
        self.show_average_only = False  # show only average curve
        self.hide_x_axis = False  # hide bottom axis for compact stacking
        self.original_x_values = None  # original grain sizes

        # Hover/pin overlays
        self.point_marker = None    # transient hover point (ScatterPlotItem)
        self.coord_label = None     # transient text label (TextItem)
        self.pinned_markers = []    # list of {'scatter':..., 'label':...}
        
        # Get visualization settings instance
        self.settings = VisualizationSettings()
        
        # Initialize settings dialog lazily
        self.settings_dialog = None
        
        self._setup_ui()
        self._plot_data()
        
        # Connect to settings changes
        self.settings.settingsChanged.connect(self._update_plot_styling)
        
    def _setup_ui(self):
        """Initialize the UI for the popup window."""
        # Title: include total groups (e.g., "Group 2 of 5")
        self.setWindowTitle(f"Group {self.group_id} of {self.total_groups}")
        
        # Setup toolbar first
        self._setup_toolbar()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 0, 10, 10)

        # Colored header bar matching group color on map
        header_bar = QFrame()
        header_bar.setFixedHeight(6)
        header_bar.setStyleSheet(f"background-color: {self.base_color}; border: none;")
        layout.addWidget(header_bar)

        # Create plot widget directly without header
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        
        # Apply initial styling from settings
        self._apply_plot_styling()
        
        # Show grid
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)

        # Group label at top-left (won't overlap data)
        self.group_label_item = pg.TextItem(
            f"Group {self.group_id} of {self.total_groups}",
            color=(80, 80, 80), anchor=(0, 0)
        )
        self.group_label_item.setFont(pg.QtGui.QFont('Arial', 11, pg.QtGui.QFont.Weight.Bold))
        self.plot_widget.addItem(self.group_label_item, ignoreBounds=True)

        layout.addWidget(self.plot_widget)

        # Connect range change for adaptive x-axis ticks + label position
        self.plot_widget.getViewBox().sigRangeChanged.connect(self._on_range_changed)
    
    def _apply_plot_styling(self):
        """Apply current settings to plot styling."""
        axis_style = self.settings.get_axis_style()
        tick_style = self.settings.get_tick_style()
        
        # Apply axis labels with settings
        self.plot_widget.setLabel('left', 'Frequency', units=self.y_unit, **axis_style)
        self.plot_widget.setLabel('bottom', 'Grain Size', units=self.x_unit, unitPrefix='', **axis_style)
        
        # Apply tick font styling
        left_axis = self.plot_widget.getAxis('left')
        bottom_axis = self.plot_widget.getAxis('bottom')
        
        # Create pens for axis
        axis_pen = pg.mkPen(color='#333', width=1)
        left_axis.setPen(axis_pen)
        bottom_axis.setPen(axis_pen)
        left_axis.setTextPen(tick_style['color'])
        bottom_axis.setTextPen(tick_style['color'])
        
        # Set tick text offset for better visibility
        left_axis.setStyle(tickTextOffset=10)
        bottom_axis.setStyle(tickTextOffset=10)
        
        # Apply tick font size using QFont
        from PyQt6.QtGui import QFont
        tick_font = QFont()
        tick_font.setPointSize(self.settings.tick_font_size)
        left_axis.setTickFont(tick_font)
        bottom_axis.setTickFont(tick_font)
    
    def _update_plot_styling(self):
        """Update plot styling when settings change."""
        self._apply_plot_styling()
        # Replot data with new line thickness
        self._plot_data()
    
    def _setup_toolbar(self):
        """Setup toolbar with scale toggle and export actions."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Scale toggle action
        self.scale_action = QAction("Switch to Linear", self)
        self.scale_action.setToolTip("Toggle between logarithmic and linear scale")
        self.scale_action.triggered.connect(self._toggle_scale)
        toolbar.addAction(self.scale_action)

        # Chart type toggle action
        self.chart_type_action = QAction("Switch to Line", self)
        self.chart_type_action.setToolTip("Toggle between bar and line chart")
        self.chart_type_action.triggered.connect(self._toggle_chart_type)
        toolbar.addAction(self.chart_type_action)

        # Clear pinned/hover points action (placed next to scale toggle)
        self.clear_points_action = QAction("Clear Markers", self)
        self.clear_points_action.setToolTip("Remove all pinned markers and hide hover label")
        self.clear_points_action.triggered.connect(self._clear_all_points)
        toolbar.addAction(self.clear_points_action)

        # Show Average Only toggle
        self.avg_action = QAction("Show Average Only", self)
        self.avg_action.setCheckable(True)
        self.avg_action.setChecked(False)
        self.avg_action.setToolTip("Show only the group average curve")
        self.avg_action.triggered.connect(self._toggle_average_only)
        toolbar.addAction(self.avg_action)

        # Hide X-Axis toggle
        self.hide_x_action = QAction("Hide X-Axis", self)
        self.hide_x_action.setCheckable(True)
        self.hide_x_action.setChecked(False)
        self.hide_x_action.setToolTip("Hide X-axis label and ticks for compact stacking")
        self.hide_x_action.triggered.connect(self._toggle_hide_x_axis)
        toolbar.addAction(self.hide_x_action)

        # Separator
        toolbar.addSeparator()

        # Apply Layout to All action
        apply_layout_action = QAction("Apply Layout to All", self)
        apply_layout_action.setToolTip("Apply current scale, chart type, and view range to all group windows")
        apply_layout_action.triggered.connect(self._apply_layout_to_all)
        toolbar.addAction(apply_layout_action)
        
        # Retile action
        retile_action = QAction("Retile Windows", self)
        retile_action.setToolTip("Retile all windows vertically")
        retile_action.triggered.connect(self._retile_windows)
        toolbar.addAction(retile_action)
        
        # Close all group detail windows
        close_all_action = QAction("Close All", self)
        close_all_action.setToolTip("Close all group detail windows")
        close_all_action.triggered.connect(self._close_all_windows)
        toolbar.addAction(close_all_action)
        
        # Separator
        toolbar.addSeparator()
        
        # Reset action (global style + all group windows to defaults)
        reset_action = QAction("Reset", self)
        reset_action.setToolTip("Reset all group detail windows and styles to defaults")
        reset_action.triggered.connect(self._reset_all_defaults)
        toolbar.addAction(reset_action)
        
        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.setToolTip("Adjust visualization settings for publication standards")
        settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(settings_action)
        
        # Separator
        toolbar.addSeparator()
        
        # Export action
        export_action = QAction("Export as PNG", self)
        export_action.setToolTip("Export current view as PNG")
        export_action.triggered.connect(self._export_as_png)
        toolbar.addAction(export_action)
    
    def _show_settings(self):
        """Show visualization settings dialog."""
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
    
    def _toggle_hide_x_axis(self, checked):
        """Toggle visibility of the bottom axis (label + ticks)."""
        self.hide_x_axis = checked
        self.plot_widget.getAxis('bottom').setVisible(not checked)

    def _toggle_average_only(self, checked):
        """Toggle showing only the group average curve. Preserves X-axis range."""
        x_range = self.plot_widget.viewRange()[0]
        self.show_average_only = checked
        self._plot_data()
        self.plot_widget.setXRange(*x_range, padding=0)

    def _toggle_scale(self):
        """Toggle between logarithmic and linear scale for X-axis."""
        self.is_log_scale = not self.is_log_scale

        if self.is_log_scale:
            self.scale_action.setText("Switch to Linear")
        else:
            self.scale_action.setText("Switch to Log")

        self._plot_data()
        self.plot_widget.autoRange()

        # Linear axis must start at 0
        if not self.is_log_scale and self.original_x_values is not None:
            x_max = float(np.max(self.original_x_values))
            self.plot_widget.setXRange(0, x_max * 1.05, padding=0)

    def _toggle_chart_type(self):
        """Toggle between bar and line chart types. Preserves X-axis range."""
        x_range = self.plot_widget.viewRange()[0]
        self.show_as_bar = not self.show_as_bar
        if self.show_as_bar:
            self.chart_type_action.setText("Switch to Line")
        else:
            self.chart_type_action.setText("Switch to Bar")
        self._plot_data()
        self.plot_widget.setXRange(*x_range, padding=0)

    def _reset_all_defaults(self):
        """Reset styles and all group detail windows to defaults."""
        # Reset shared visualization styles
        try:
            self.settings.reset_to_defaults()
        except Exception:
            pass
        # Reset this window's toggles
        self.is_log_scale = True
        self.show_as_bar = True
        self.show_average_only = False
        self.hide_x_axis = False
        # Update toolbar texts
        try:
            self.scale_action.setText("Switch to Linear")
            self.chart_type_action.setText("Switch to Line")
            self.avg_action.setChecked(False)
            self.hide_x_action.setChecked(False)
            self.plot_widget.getAxis('bottom').setVisible(True)
        except Exception:
            pass
        # Replot and reset view
        self._clear_all_points()
        self._plot_data()
        self.plot_widget.autoRange()
        
        # Apply same layout to all windows via manager
        try:
            if self.manager:
                self.manager.apply_layout_to_all(self.get_layout_settings())
        except Exception:
            pass
        
    def _apply_layout_to_all(self):
        """Apply current window's layout settings to all group windows."""
        if not self.manager:
            return
        
        # Gather current layout settings
        settings = self.get_layout_settings()
        
        # Apply to all windows via manager
        self.manager.apply_layout_to_all(settings)
        
        # Show confirmation in window title temporarily
        original_title = self.windowTitle()
        self.setWindowTitle(f"{original_title} - Layout applied to all!")
        QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
    
    def _retile_windows(self):
        """Retile all windows."""
        if not self.manager:
            return
        self.manager._tile_windows_vertically()
    
    def _close_all_windows(self):
        """Close all group detail windows via manager."""
        if not self.manager:
            return
        self.manager.close_all()
    
    def get_layout_settings(self):
        """Get current layout settings as a dictionary."""
        view_range = self.plot_widget.viewRange()
        geom = self.geometry()
        return {
            'is_log_scale': self.is_log_scale,
            'show_as_bar': self.show_as_bar,
            'show_average_only': self.show_average_only,
            'hide_x_axis': self.hide_x_axis,
            'x_range': view_range[0],
            'y_range': view_range[1],
            'window_width': geom.width(),
            'window_height': geom.height(),
        }

    def get_full_state(self) -> dict:
        """Return full JSON-safe state for session save/restore.

        Includes layout settings, window geometry (hex of saveGeometry),
        and pinned markers serialized without Qt objects.
        """
        view_range = self.plot_widget.viewRange()
        try:
            geom_hex = bytes(self.saveGeometry()).hex()
        except Exception:
            geom_hex = ""
        # Serialize pinned markers, dropping Qt objects
        pms = []
        for m in self.pinned_markers:
            pms.append({
                "sample_name": m.get("sample_name"),
                "x_plot": m.get("x_plot"),
                "y_plot": m.get("y_plot"),
            })
        return {
            "is_log_scale": self.is_log_scale,
            "show_as_bar": self.show_as_bar,
            "show_average_only": self.show_average_only,
            "hide_x_axis": self.hide_x_axis,
            "x_range": list(view_range[0]),
            "y_range": list(view_range[1]),
            "geometry": geom_hex,
            "pinned_markers": pms,
        }

    def apply_full_state(self, state: dict) -> None:
        """Restore the full state captured by get_full_state()."""
        if not isinstance(state, dict):
            return
        # Reuse existing apply_layout_settings for the layout/view fields
        self.apply_layout_settings(state)
        # Restore window geometry from hex
        geom_hex = state.get("geometry") or ""
        if geom_hex:
            try:
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray(bytes.fromhex(geom_hex)))
            except (ValueError, Exception):
                pass
        # Restore pinned markers (clear existing first)
        try:
            self._clear_pinned_points()
        except Exception:
            pass
        for m in state.get("pinned_markers", []) or []:
            sample_name = m.get("sample_name")
            x_plot = m.get("x_plot")
            y_plot = m.get("y_plot")
            x_disp = m.get("x_disp")
            y_disp = m.get("y_disp")
            if sample_name is None or x_plot is None or y_plot is None:
                continue
            # Recompute display values if not saved (depends on current scale)
            if x_disp is None:
                x_disp = (10 ** x_plot) if self.is_log_scale else x_plot
            if y_disp is None:
                y_disp = y_plot
            try:
                self._pin_point(float(x_plot), float(y_plot),
                                float(x_disp), float(y_disp), str(sample_name))
            except Exception:
                pass

    def apply_layout_settings(self, settings):
        """Apply layout settings from another window."""
        # Apply scale
        if settings.get('is_log_scale') != self.is_log_scale:
            self._toggle_scale()

        # Apply chart type
        if settings.get('show_as_bar') != self.show_as_bar:
            self._toggle_chart_type()

        # Apply average-only toggle
        if settings.get('show_average_only', False) != self.show_average_only:
            self.show_average_only = settings['show_average_only']
            self.avg_action.setChecked(self.show_average_only)
            self._plot_data()

        # Apply hide x-axis toggle
        if settings.get('hide_x_axis', False) != self.hide_x_axis:
            self.hide_x_axis = settings['hide_x_axis']
            self.hide_x_action.setChecked(self.hide_x_axis)
            self.plot_widget.getAxis('bottom').setVisible(not self.hide_x_axis)

        # Apply view range
        if 'x_range' in settings and 'y_range' in settings:
            self.plot_widget.setRange(xRange=settings['x_range'], yRange=settings['y_range'], padding=0)

        # Apply window size
        if 'window_width' in settings and 'window_height' in settings:
            self.resize(settings['window_width'], settings['window_height'])
    
    def _export_as_png(self):
        """Export the current plot as PNG image."""
        # Create file dialog for saving
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export Group {self.group_id} as PNG",
            f"group_{self.group_id}_grain_distribution.png",
            "PNG Files (*.png)"
        )
        
        if file_path:
            # Get the central widget which contains the plot
            central_widget = self.centralWidget()
            pixmap = central_widget.grab()
            
            # Save the pixmap
            if pixmap.save(file_path):
                print(f"Successfully exported to {file_path}")
                # Show status in window title temporarily
                original_title = self.windowTitle()
                self.setWindowTitle(f"{original_title} - Exported!")
                QTimer.singleShot(2000, lambda: self.setWindowTitle(original_title))
            else:
                print(f"Failed to export to {file_path}")
    
    def _plot_data(self):
        """Plot sample curves and prepare overlays."""
        # Store original x values
        if self.original_x_values is None:
            self.original_x_values = self.x_values.copy()

        # Convert color to RGBA (fully opaque for sample lines)
        color = pg.mkColor(self.base_color)
        r, g, b, _ = color.getRgb()

        # Clear plot and state
        self.plot_widget.clear()
        self.plot_items = []
        self._clear_pinned_points()

        # Re-add group label (clear() removes all items)
        self.group_label_item = pg.TextItem(
            f"Group {self.group_id} of {self.total_groups}",
            color=(80, 80, 80), anchor=(0, 0)
        )
        self.group_label_item.setFont(pg.QtGui.QFont('Arial', 11, pg.QtGui.QFont.Weight.Bold))
        self.plot_widget.addItem(self.group_label_item, ignoreBounds=True)

        # If showing average only, replace samples with single average
        if self.show_average_only and len(self.samples) > 0:
            all_values = np.array([s['values'] for s in self.samples])
            mean_psd = np.mean(all_values, axis=0)
            samples_to_plot = [{'name': 'Average', 'values': mean_psd.tolist()}]
        else:
            samples_to_plot = self.samples
        self.point_marker = None
        self.coord_label = None
        
        # Plot individual sample lines based on scale
        if self.is_log_scale:
            # Use log scale for x-axis (handle zero/negative values)
            x_plot_values = np.where(self.original_x_values > 0, 
                                    np.log10(self.original_x_values), 
                                    np.nan)
            # Filter out NaN values
            valid_mask = ~np.isnan(x_plot_values)
            
            for si, sample in enumerate(samples_to_plot):
                    y_values = np.array(sample['values'])
                    
                    # Ensure y_values and x_plot_values have the same length
                    if len(y_values) != len(x_plot_values):
                        # Truncate or pad to match
                        min_len = min(len(y_values), len(x_plot_values))
                        y_values = y_values[:min_len]
                        x_plot_subset = x_plot_values[:min_len]
                        valid_mask_subset = valid_mask[:min_len]
                    else:
                        x_plot_subset = x_plot_values
                        valid_mask_subset = valid_mask
                    
                    if self.show_as_bar:
                        # Bar chart rendering (semi-transparent fill + thin outline)
                        base_w = self._compute_bar_widths(x_plot_subset[valid_mask_subset])
                        w = base_w * float(self.settings.bar_width_scale)
                        default_brush = pg.mkBrush(r, g, b, 120)
                        hover_brush = pg.mkBrush(r, g, b, 220)
                        bar_pen = pg.mkPen(r, g, b, 180)
                        bar_item = pg.BarGraphItem(
                            x=x_plot_subset[valid_mask_subset],
                            height=y_values[valid_mask_subset],
                            width=w,
                            brush=default_brush,
                            pen=bar_pen
                        )
                        self.plot_widget.addItem(bar_item)
                        
                        # Invisible line for interaction hit-testing
                        line_pen = pg.mkPen(color=(0, 0, 0, 0), width=0.001)
                        plot_item = self.plot_widget.plot(
                            x_plot_subset[valid_mask_subset],
                            y_values[valid_mask_subset],
                            pen=line_pen
                        )
                        hover_width = self.settings.line_thickness + 1.5
                        click_width = self.settings.line_thickness + 1.0
                        self.plot_items.append({
                            'plot_item': plot_item,
                            'bar_item': bar_item,
                            'sample_name': sample['name'],
                            'original_pen': line_pen,
                            'hover_pen': pg.mkPen(color=(r, g, b, 255), width=hover_width),
                            'click_pen': pg.mkPen(color=(255, 165, 0, 255), width=click_width),
                            'default_brush': default_brush,
                            'hover_brush': hover_brush,
                            'default_bar_pen': bar_pen,
                            'bar_x': x_plot_subset[valid_mask_subset],
                            'bar_w': w,
                            'bar_h': y_values[valid_mask_subset],
                            'y0': 0.0
                        })
                    else:
                        # Line chart rendering with distinct color per sample
                        line_color = pg.intColor(si, hues=max(10, len(samples_to_plot)), alpha=255)
                        pen = pg.mkPen(color=line_color, width=self.settings.line_thickness)
                        plot_item = self.plot_widget.plot(x_plot_subset[valid_mask_subset],
                                                         y_values[valid_mask_subset],
                                                         pen=pen)

                        hover_width = self.settings.line_thickness + 1.5
                        click_width = self.settings.line_thickness + 1.0
                        self.plot_items.append({
                            'plot_item': plot_item,
                            'sample_name': sample['name'],
                            'original_pen': pen,
                            'hover_pen': pg.mkPen(color=line_color, width=hover_width),
                            'click_pen': pg.mkPen(color=(255, 165, 0, 255), width=click_width)
                        })
        else:
            # Linear scale - use actual grain-size x-values instead of indices
            x_plot_values = self.original_x_values.astype(float)
            
            for si, sample in enumerate(samples_to_plot):
                y_values = np.array(sample['values'])
                # Ensure lengths match
                if len(y_values) != len(x_plot_values):
                    min_len = min(len(y_values), len(x_plot_values))
                    y_values = y_values[:min_len]
                    x_plot_subset = x_plot_values[:min_len]
                else:
                    x_plot_subset = x_plot_values
                
                if self.show_as_bar:
                    # Bar chart rendering on actual x positions
                    base_w = self._compute_bar_widths(x_plot_subset)
                    w = base_w * float(self.settings.bar_width_scale)
                    default_brush = pg.mkBrush(r, g, b, 120)
                    hover_brush = pg.mkBrush(r, g, b, 220)
                    bar_pen = pg.mkPen(r, g, b, 180)
                    bar_item = pg.BarGraphItem(
                        x=x_plot_subset,
                        height=y_values,
                        width=w,
                        brush=default_brush,
                        pen=bar_pen
                    )
                    self.plot_widget.addItem(bar_item)
                    
                    # Invisible line for interaction
                    line_pen = pg.mkPen(color=(0, 0, 0, 0), width=0.001)
                    plot_item = self.plot_widget.plot(x_plot_subset, y_values, pen=line_pen)
                    hover_width = self.settings.line_thickness + 1.5
                    click_width = self.settings.line_thickness + 1.0
                    self.plot_items.append({
                        'plot_item': plot_item,
                        'bar_item': bar_item,
                        'sample_name': sample['name'],
                        'original_pen': line_pen,
                        'hover_pen': pg.mkPen(color=(r, g, b, 255), width=hover_width),
                        'click_pen': pg.mkPen(color=(255, 165, 0, 255), width=click_width),
                        'default_brush': default_brush,
                        'hover_brush': hover_brush,
                        'default_bar_pen': bar_pen,
                        'bar_x': x_plot_subset,
                        'bar_w': w,
                        'bar_h': y_values,
                        'y0': 0.0
                    })
                else:
                    # Line chart rendering on actual x positions with per-sample color
                    line_color = pg.intColor(si, hues=max(10, len(samples_to_plot)), alpha=255)
                    pen = pg.mkPen(color=line_color, width=self.settings.line_thickness)
                    plot_item = self.plot_widget.plot(x_plot_subset, y_values, pen=pen)
                    
                    hover_width = self.settings.line_thickness + 1.5
                    click_width = self.settings.line_thickness + 1.0
                    self.plot_items.append({
                        'plot_item': plot_item,
                        'sample_name': sample['name'],
                        'original_pen': pen,
                        'hover_pen': pg.mkPen(color=line_color, width=hover_width),  # Thicker for hover
                        'click_pen': pg.mkPen(color=(255, 165, 0, 255), width=click_width)  # Orange for click feedback
                    })
        
        # Update x-axis ticks after plotting
        self._update_x_ticks()

        # Position group label at top-left of current view
        if hasattr(self, 'group_label_item'):
            vr = self.plot_widget.viewRange()
            self.group_label_item.setPos(vr[0][0], vr[1][1])

        # Connect click and hover events (avoid duplicates)
        scene = self.plot_widget.scene()
        try:
            scene.sigMouseClicked.disconnect(self._on_plot_clicked)
        except Exception:
            pass
        try:
            scene.sigMouseMoved.disconnect(self._on_mouse_hover)
        except Exception:
            pass
        scene.sigMouseClicked.connect(self._on_plot_clicked)
        scene.sigMouseMoved.connect(self._on_mouse_hover)

        # Ensure transient overlay items exist (created lazily on first hover)
        

    def _on_range_changed(self, *args):
        """Update x-axis ticks and group label position when view range changes."""
        self._update_x_ticks()
        # Reposition group label to top-left of visible area
        if hasattr(self, 'group_label_item'):
            vr = self.plot_widget.viewRange()
            self.group_label_item.setPos(vr[0][0], vr[1][1])
        
    def _update_x_ticks(self):
        """Adaptive x-axis tick labeling depending on zoom level and scale type."""
        ax = self.plot_widget.getAxis('bottom')
        vb = self.plot_widget.getViewBox()

        if self.is_log_scale:
            major = []
            minor = []

            if self.original_x_values is not None and len(self.original_x_values) > 0:
                min_val = np.min(self.original_x_values[self.original_x_values > 0])
                max_val = np.max(self.original_x_values)

                log_min = np.floor(np.log10(min_val))
                log_max = np.ceil(np.log10(max_val))

                for exp in range(int(log_min), int(log_max) + 1):
                    val = 10 ** exp
                    if min_val <= val <= max_val:
                        log_pos = np.log10(val)
                        if val >= 1:
                            label = f"{int(val)}" if val == int(val) else f"{val:.1f}"
                        else:
                            label = f"{val:.2f}" if val >= 0.1 else f"{val:.3f}"
                        major.append((log_pos, label))

                    # Minor ticks at 2,3,4,5,6,7,8,9 × 10^exp
                    for mult in range(2, 10):
                        mval = mult * (10 ** exp)
                        if min_val <= mval <= max_val:
                            minor.append((np.log10(mval), ''))

            ax.setTicks([major, minor])
        else:
            if self.original_x_values is not None and len(self.original_x_values) > 0:
                data_min = float(np.min(self.original_x_values))
                data_max = float(np.max(self.original_x_values))
                if not np.isfinite(data_min) or not np.isfinite(data_max) or data_max <= data_min:
                    return
                vr = vb.viewRange()[0]
                min_val = max(data_min, float(vr[0]))
                max_val = min(data_max, float(vr[1]))
                if max_val <= min_val:
                    min_val, max_val = data_min, data_max

                major = self._nice_linear_ticks(min_val, max_val, desired=7)
                minor = self._nice_linear_minor_ticks(major, min_val, max_val)
                ax.setTicks([major, minor])

        ax.setTextPen('#333')

    def _nice_linear_ticks(self, vmin: float, vmax: float, desired: int = 7):
        """Compute 'nice' evenly spaced linear ticks for [vmin, vmax].
        Returns list[(pos,label)].
        """
        import math
        span = vmax - vmin
        if span <= 0:
            return []
        # Initial rough step
        raw = span / max(2, desired)
        exp = math.floor(math.log10(raw))
        base = 10 ** exp
        candidates = [1, 2, 5, 10]
        step = min(candidates, key=lambda m: abs(raw - m * base)) * base
        # Snap start to multiple of step
        start = math.floor(vmin / step) * step
        end = math.ceil(vmax / step) * step
        
        # Generate ticks
        ticks = []
        x = start
        # Guard against infinite loop due to FP error
        max_iter = 100
        it = 0
        while x <= end + 1e-9 and it < max_iter:
            if vmin - 1e-9 <= x <= vmax + 1e-9:
                # Adaptive label format
                label = self._format_number(x)
                ticks.append((x, label))
            x += step
            it += 1
        return ticks

    @staticmethod
    def _nice_linear_minor_ticks(major_ticks, vmin, vmax):
        """Generate minor ticks between major ticks (subdivide each interval into 5)."""
        if len(major_ticks) < 2:
            return []
        step = major_ticks[1][0] - major_ticks[0][0]
        if step <= 0:
            return []
        minor_step = step / 5
        minor = []
        start = major_ticks[0][0] - step
        end = major_ticks[-1][0] + step
        x = start
        while x <= end + 1e-9:
            if vmin - 1e-9 <= x <= vmax + 1e-9:
                is_major = any(abs(x - mt[0]) < minor_step * 0.1 for mt in major_ticks)
                if not is_major:
                    minor.append((x, ''))
            x += minor_step
        return minor

    def _compute_bar_widths(self, x_positions: np.ndarray) -> np.ndarray:
        """Compute bar widths based on neighbor gaps in plotted x-coordinates.
        Works for both linear (indices) and log-transformed x positions.
        """
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
    
    # ===== Overlay helpers =====
    def _format_number(self, v: float) -> str:
        """Adaptive numeric format."""
        if v is None:
            return ""
        if abs(v) >= 100:
            return f"{v:.0f}"
        if abs(v) >= 1:
            return f"{v:.1f}"
        if abs(v) >= 0.1:
            return f"{v:.2f}"
        return f"{v:.3f}"

    def _ensure_hover_items(self):
        """Create hover marker and label if missing."""
        if self.point_marker is None:
            self.point_marker = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(255, 0, 0, 180), pen=pg.mkPen(None))
            self.plot_widget.addItem(self.point_marker)
        if self.coord_label is None:
            self.coord_label = pg.TextItem(color=(20, 20, 20))
            self.coord_label.setAnchor((0, 1))
            self.plot_widget.addItem(self.coord_label)

    def _clear_hover_overlays(self):
        """Hide transient hover marker and text."""
        if self.point_marker is not None:
            self.point_marker.setData([], [])
        if self.coord_label is not None:
            self.coord_label.setText("")

    def _update_hover_display(self, x_plot, y_plot, x_disp, y_disp, sample_name: str):
        """Update transient hover point and text."""
        self._ensure_hover_items()
        self.point_marker.setData([x_plot], [y_plot])
        x_txt = self._format_number(x_disp)
        y_txt = self._format_number(y_disp)
        self.coord_label.setText(f"{x_txt} {self.x_unit}, {y_txt} {self.y_unit} — {sample_name}")
        self.coord_label.setPos(x_plot, y_plot)

    def _find_existing_marker(self, x_plot, y_plot, sample_name):
        """Find an existing pinned marker at the same position for the same sample.
        Returns index into self.pinned_markers, or -1 if not found."""
        for i, marker in enumerate(self.pinned_markers):
            if marker.get('sample_name') == sample_name:
                if abs(marker['x_plot'] - x_plot) < 1e-4 and abs(marker['y_plot'] - y_plot) < 1e-4:
                    return i
        return -1

    def _remove_pinned_marker(self, index):
        """Remove a single pinned marker by index."""
        marker = self.pinned_markers.pop(index)
        try:
            self.plot_widget.removeItem(marker['scatter'])
            self.plot_widget.removeItem(marker['label'])
        except Exception:
            pass

    def _pin_point(self, x_plot, y_plot, x_disp, y_disp, sample_name: str):
        """Toggle persistent marker+label at a point: add if absent, remove if present."""
        # Check for existing marker at this position — toggle off if found
        existing = self._find_existing_marker(x_plot, y_plot, sample_name)
        if existing >= 0:
            import time
            self._remove_pinned_marker(existing)
            self._just_unpinned = time.time()
            return False  # marker was removed

        scatter = pg.ScatterPlotItem(size=7, brush=pg.mkBrush(0, 150, 136, 200), pen=pg.mkPen(0, 121, 107), symbol='o')
        scatter.setData([x_plot], [y_plot])
        label = pg.TextItem(color=(0, 100, 90))
        label.setAnchor((0, 1))
        x_txt = self._format_number(x_disp)
        y_txt = self._format_number(y_disp)
        label.setText(f"{x_txt} {self.x_unit}, {y_txt} {self.y_unit} — {sample_name}")
        label.setPos(x_plot, y_plot)
        self.plot_widget.addItem(scatter)
        self.plot_widget.addItem(label)
        self.pinned_markers.append({
            'scatter': scatter, 'label': label,
            'sample_name': sample_name, 'x_plot': x_plot, 'y_plot': y_plot
        })
        return True  # marker was added

    def _clear_pinned_points(self):
        """Remove all pinned overlays."""
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
        """Clear pinned points and hide hover overlays."""
        self._clear_pinned_points()
        self._clear_hover_overlays()

    def _emit_hover(self, sample_name):
        """Emit hover signal, avoiding redundant emissions."""
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
        """Highlight a specific sample's curve/bar (called from map hover)."""
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
        """Reset all curves to default pens (called when map hover leaves)."""
        self._external_highlight = None
        for item_data in self.plot_items:
            item_data['plot_item'].setPen(item_data['original_pen'])
            if 'bar_item' in item_data:
                item_data['bar_item'].setOpts(
                    brush=item_data.get('default_brush'),
                    pen=item_data.get('default_bar_pen')
                )

    def _on_plot_clicked(self, event):
        """Handle mouse clicks: left to pin a point, right to clear pins."""
        if event.button() == Qt.MouseButton.RightButton:
            # Clear all pinned overlays
            self._clear_pinned_points()
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Scene -> data coords
            pos = event.scenePos()
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_click = mouse_point.x()
            y_click = mouse_point.y()
            
        # If bar mode, first try rectangle hit-testing so clicking anywhere on a bar works
        if self.show_as_bar:
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
                        # Inside this bar: treat as selection at bar top
                        x_plot = float(xs[idx])
                        y_plot = float(y_top)
                        # Convert plotted x to display
                        if self.is_log_scale:
                            x_disp = 10 ** x_plot
                        else:
                            x_disp = float(xs[idx])
                        y_disp = float(y_top)
                        # Flash and pin
                        plot_item = item_data['plot_item']
                        click_pen = item_data['click_pen']
                        original_pen = item_data['original_pen']
                        plot_item.setPen(click_pen)
                        original_bar_pen = item_data.get('default_bar_pen')
                        item_data['bar_item'].setOpts(pen=pg.mkPen(255, 165, 0, 255))
                        def reset_color():
                            plot_item.setPen(original_pen)
                            item_data['bar_item'].setOpts(pen=original_bar_pen)
                        QTimer.singleShot(200, reset_color)
                        pinned = self._pin_point(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
                        if pinned:
                            self.lineClicked.emit(item_data['sample_name'])
                        return  # handled
        
        # Fallback: Find closest point across all curves
        min_distance = float('inf')
        closest = None  # tuple(item_data, min_idx)
        
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
            
            # Convert plotted x to real grain size
            if self.is_log_scale:
                x_disp = 10 ** x_plot
            else:
                # linear mode plots at actual grain sizes, so x_plot is the value
                x_disp = float(x_plot)
            y_disp = float(y_plot)
            
            # Visual click feedback
            click_pen = item_data['click_pen']
            original_pen = item_data['original_pen']
            plot_item.setPen(click_pen)
            # Also flash bar outline if present
            if 'bar_item' in item_data:
                original_bar_pen = item_data.get('default_bar_pen')
                item_data['bar_item'].setOpts(pen=pg.mkPen(255, 165, 0, 255))
            def reset_color():
                plot_item.setPen(original_pen)
                if 'bar_item' in item_data:
                    item_data['bar_item'].setOpts(pen=original_bar_pen)
            QTimer.singleShot(200, reset_color)
            
            # Toggle marker at this point
            pinned = self._pin_point(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])

            # Emit which sample was clicked (only when pinning, not unpinning)
            if pinned:
                self.lineClicked.emit(item_data['sample_name'])
    
    def _on_mouse_hover(self, pos):
        """Hover: highlight nearest curve and show point coordinates."""
        import time
        # Skip hover briefly after unpinning to avoid re-flash
        if hasattr(self, '_just_unpinned') and time.time() - self._just_unpinned < 0.3:
            self._clear_hover_overlays()
            self._emit_hover(None)
            return

        # Scene -> data coordinates
        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        x_hover = mouse_point.x()
        y_hover = mouse_point.y()
        
        # Normalized distance for scale-invariant hit testing
        x_range = self.plot_widget.viewRange()[0]
        y_range = self.plot_widget.viewRange()[1]
        x_scale = x_range[1] - x_range[0] if x_range[1] != x_range[0] else 1
        y_scale = y_range[1] - y_range[0] if y_range[1] != y_range[0] else 1
        
        min_distance = float('inf')
        closest = None  # tuple(item_data, min_idx)
        
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
        
        # Reset pens and bar brushes
        for item_data in self.plot_items:
            item_data['plot_item'].setPen(item_data['original_pen'])
            if 'bar_item' in item_data:
                # Reset bar visual to default
                item_data['bar_item'].setOpts(
                    brush=item_data.get('default_brush'),
                    pen=item_data.get('default_bar_pen')
                )
        
        # If bar mode, try rectangle hover first
        if self.show_as_bar:
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
                        # Hovering over this bar
                        plot_item = item_data['plot_item']
                        plot_item.setPen(item_data['hover_pen'])
                        item_data['bar_item'].setOpts(brush=item_data.get('hover_brush'))
                        x_plot = float(xs[idx])
                        y_plot = float(y_top)
                        if self.is_log_scale:
                            x_disp = 10 ** x_plot
                        else:
                            x_disp = float(xs[idx])
                        y_disp = float(y_top)
                        self._update_hover_display(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
                        self._emit_hover(item_data['sample_name'])
                        return

        if closest and min_distance < 0.06:
            item_data, idx = closest
            plot_item = item_data['plot_item']
            x_data, y_data = plot_item.getData()
            x_plot = float(x_data[idx])
            y_plot = float(y_data[idx])
            
            # Highlight the curve under hover
            plot_item.setPen(item_data['hover_pen'])
            if 'bar_item' in item_data:
                # Emphasize bar brush on hover
                item_data['bar_item'].setOpts(brush=item_data.get('hover_brush'))
            
            # Convert to display values (real grain size, original y)
            if self.is_log_scale:
                x_disp = 10 ** x_plot
            else:
                x_disp = float(x_plot)
            y_disp = float(y_plot)
            
            # Update transient hover marker + text
            self._update_hover_display(x_plot, y_plot, x_disp, y_disp, item_data['sample_name'])
            self._emit_hover(item_data['sample_name'])
        else:
            # Hide hover overlays when not near any curve
            if self.point_marker is not None:
                self.point_marker.setData([], [])
            if self.coord_label is not None:
                self.coord_label.setText("")
            self._emit_hover(None)
