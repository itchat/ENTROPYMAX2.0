"""
Dialog for manually relabeling group numbers after clustering.
"""

import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QComboBox, QPushButton, QDialogButtonBox,
                             QFrame, QWidget, QColorDialog, QScrollArea)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from utils.color_gradient import brown_yellow_gradient


def _compute_group_mean_grain_size(samples, x_labels):
    """Compute weighted mean grain size for a group."""
    try:
        grain_sizes = np.array([float(l.replace('μm', '').replace('um', '').strip()) for l in x_labels])
        all_values = np.array([s['values'] for s in samples])
        mean_psd = np.mean(all_values, axis=0)
        total = np.sum(mean_psd)
        if total > 0:
            return float(np.sum(grain_sizes * mean_psd) / total)
    except Exception:
        pass
    return 0.0


def _compute_group_peak_bin(samples, x_labels):
    """Compute the grain size of the peak (highest frequency) bin for a group."""
    try:
        grain_sizes = np.array([float(l.replace('μm', '').replace('um', '').strip()) for l in x_labels])
        all_values = np.array([s['values'] for s in samples])
        mean_psd = np.mean(all_values, axis=0)
        peak_idx = int(np.argmax(mean_psd))
        return float(grain_sizes[peak_idx])
    except Exception:
        pass
    return 0.0


class RelabelGroupsDialog(QDialog):
    """Dialog for relabeling group numbers with summary statistics."""

    def __init__(self, group_details, k_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Relabel Groups")
        self.k_value = k_value
        self.group_details = group_details
        self.combos = {}
        self.color_buttons = {}
        self.row_labels = {}

        self.colors = brown_yellow_gradient(self.k_value)

        # Compute stats per group
        self.group_stats = {}
        x_labels = None
        for gid, details in group_details.items():
            if x_labels is None:
                x_labels = details.get('x_labels', [])
            mean_gs = _compute_group_mean_grain_size(details['samples'], x_labels or [])
            peak_gs = _compute_group_peak_bin(details['samples'], x_labels or [])
            self.group_stats[gid] = {
                'mean_grain_size': mean_gs,
                'peak_grain_size': peak_gs,
                'count': details.get('count', len(details['samples']))
            }

        self._current_sort = 'peak'  # default sort by peak bin
        self.sorted_groups = self._sort_groups('peak')

        self._setup_ui()
        self._set_default_mapping()
        self._validate()

    def _sort_groups(self, mode):
        key = 'peak_grain_size' if mode == 'peak' else 'mean_grain_size'
        return sorted(
            self.group_stats.keys(),
            key=lambda g: self.group_stats[g][key],
            reverse=True
        )

    def _make_swatch_style(self, hex_color):
        return (
            f"background-color: {hex_color}; border: 1px solid #888; "
            f"border-radius: 3px; min-width: 28px; min-height: 22px; max-width: 28px; max-height: 22px;"
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel(
            f"Relabel {self.k_value} groups.\n"
            "Assign new label numbers using the dropdowns.\n"
            "Click the colour swatch to choose a custom colour."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #333; font-size: 13px; padding: 5px;")
        layout.addWidget(header)

        # Sort option
        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("Sort by:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Peak Bin Size", "Mean Grain Size"])
        self.sort_combo.setCurrentIndex(0)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addStretch()
        layout.addLayout(sort_layout)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #d0d0d0;")
        layout.addWidget(line)

        # Color legend
        self.legend_buttons = {}
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("Colour scale:"))
        for i in range(1, self.k_value + 1):
            btn = QPushButton(f" {i} ")
            btn.setStyleSheet(
                f"background-color: {self.colors[i]}; color: white; "
                f"font-weight: bold; border-radius: 3px; padding: 2px 6px; border: 1px solid #666;"
            )
            btn.setToolTip(f"Click to change colour for label {i}")
            btn.clicked.connect(lambda checked, label=i: self._pick_legend_color(label))
            legend_layout.addWidget(btn)
            self.legend_buttons[i] = btn
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        # Scrollable form area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_widget = QWidget()
        self.form_layout = QFormLayout(self.scroll_widget)
        self.form_layout.setSpacing(8)
        self._build_form_rows()
        self.scroll_area.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll_area, 1)  # stretch=1 so form gets available space

        # Warning label (outside scroll)
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #f44336; font-size: 12px; padding: 5px;")
        layout.addWidget(self.warning_label)

        # Buttons (outside scroll — always visible)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

    def _build_form_rows(self):
        """Build or rebuild form rows based on current sort order."""
        # Clear existing rows
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)
        self.combos.clear()
        self.color_buttons.clear()
        self.row_labels.clear()

        for gid in self.sorted_groups:
            stats = self.group_stats[gid]
            mean_gs = stats['mean_grain_size']
            peak_gs = stats['peak_grain_size']
            count = stats['count']

            label_text = f"Original Group {gid}  —  peak: {peak_gs:.1f} μm, mean: {mean_gs:.1f} μm, {count} samples"
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 13px;")
            self.row_labels[gid] = label

            combo = QComboBox()
            combo.setFixedWidth(80)
            for i in range(1, self.k_value + 1):
                combo.addItem(str(i))
            combo.currentIndexChanged.connect(self._validate)
            combo.currentIndexChanged.connect(lambda idx, g=gid: self._update_row_swatch(g))
            self.combos[gid] = combo

            swatch_btn = QPushButton()
            swatch_btn.setToolTip("Click to change this group's colour")
            swatch_btn.clicked.connect(lambda checked, g=gid: self._pick_row_color(g))
            self.color_buttons[gid] = swatch_btn

            row_layout = QHBoxLayout()
            row_layout.addWidget(label)
            row_layout.addStretch()
            row_layout.addWidget(QLabel("→ New label:"))
            row_layout.addWidget(combo)
            row_layout.addWidget(swatch_btn)

            row_widget = QWidget()
            row_widget.setLayout(row_layout)
            self.form_layout.addRow(row_widget)

    def _on_sort_changed(self, index):
        """Re-sort groups when sort option changes."""
        mode = 'peak' if index == 0 else 'mean'
        if mode == self._current_sort:
            return
        self._current_sort = mode
        self.sorted_groups = self._sort_groups(mode)
        self._build_form_rows()
        self._set_default_mapping()
        self._validate()

    def _set_default_mapping(self):
        for rank, gid in enumerate(self.sorted_groups):
            self.combos[gid].setCurrentIndex(rank)
        self._update_all_swatches()

    def _update_all_swatches(self):
        for gid in self.combos:
            self._update_row_swatch(gid)

    def _update_row_swatch(self, gid):
        if gid not in self.combos:
            return
        label_num = int(self.combos[gid].currentText())
        hex_color = self.colors.get(label_num, '#888888')
        self.color_buttons[gid].setStyleSheet(self._make_swatch_style(hex_color))

    def _update_legend(self):
        for i, btn in self.legend_buttons.items():
            btn.setStyleSheet(
                f"background-color: {self.colors[i]}; color: white; "
                f"font-weight: bold; border-radius: 3px; padding: 2px 6px; border: 1px solid #666;"
            )

    def _pick_legend_color(self, label_num):
        current = QColor(self.colors.get(label_num, '#888888'))
        color = QColorDialog.getColor(current, self, f"Choose colour for label {label_num}")
        if color.isValid():
            self.colors[label_num] = color.name()
            self._update_legend()
            self._update_all_swatches()

    def _pick_row_color(self, gid):
        label_num = int(self.combos[gid].currentText())
        current = QColor(self.colors.get(label_num, '#888888'))
        color = QColorDialog.getColor(current, self, f"Choose colour for label {label_num}")
        if color.isValid():
            self.colors[label_num] = color.name()
            self._update_legend()
            self._update_all_swatches()

    def _validate(self):
        values = []
        for gid, combo in self.combos.items():
            values.append(int(combo.currentText()))

        duplicates = len(values) != len(set(values))
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)

        if duplicates:
            self.warning_label.setText("⚠ Duplicate labels detected — each group must have a unique label.")
            ok_button.setEnabled(False)
            seen = {}
            for gid, combo in self.combos.items():
                val = int(combo.currentText())
                if val in seen:
                    combo.setStyleSheet("border: 2px solid #f44336; border-radius: 3px;")
                    seen[val].setStyleSheet("border: 2px solid #f44336; border-radius: 3px;")
                else:
                    combo.setStyleSheet("")
                    seen[val] = combo
        else:
            self.warning_label.setText("")
            ok_button.setEnabled(True)
            for combo in self.combos.values():
                combo.setStyleSheet("")

    def get_mapping(self):
        mapping = {}
        for gid, combo in self.combos.items():
            mapping[gid] = int(combo.currentText())
        return mapping

    def get_colors(self):
        return dict(self.colors)
