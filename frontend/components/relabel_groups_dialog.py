"""
Dialog for manually relabeling group numbers after clustering.
"""

import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLabel, QComboBox, QPushButton, QDialogButtonBox,
                             QFrame, QWidget, QColorDialog)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from utils.color_gradient import brown_yellow_gradient


def _compute_group_mean_grain_size(samples, x_labels):
    """
    Compute mean grain size for a group using weighted average across all samples.

    Args:
        samples: List of {'name': str, 'values': list[float]}
        x_labels: List of grain size labels (strings like '0.1', '100', etc.)

    Returns:
        Mean grain size as float, or 0.0 if computation fails.
    """
    try:
        grain_sizes = []
        for label in x_labels:
            val = label.replace('μm', '').replace('um', '').strip()
            grain_sizes.append(float(val))
        grain_sizes = np.array(grain_sizes)

        # Average the PSD across all samples in the group
        all_values = np.array([s['values'] for s in samples])
        mean_psd = np.mean(all_values, axis=0)

        # Weighted mean grain size
        total = np.sum(mean_psd)
        if total > 0:
            return float(np.sum(grain_sizes * mean_psd) / total)
    except Exception:
        pass
    return 0.0


class RelabelGroupsDialog(QDialog):
    """Dialog for relabeling group numbers with summary statistics."""

    def __init__(self, group_details, k_value, parent=None):
        """
        Args:
            group_details: Dict from DataPipeline.extract_group_details()
                {group_id: {'samples': [...], 'x_labels': [...], 'count': N}}
            k_value: Number of groups (K)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Relabel Groups")
        self.k_value = k_value
        self.group_details = group_details
        self.combos = {}  # {original_group_id: QComboBox}
        self.color_buttons = {}  # {original_group_id: QPushButton}

        # Initialize colors from brown-yellow gradient
        self.colors = brown_yellow_gradient(self.k_value)  # {label: hex}

        # Compute mean grain size per group
        self.group_stats = {}
        x_labels = None
        for gid, details in group_details.items():
            if x_labels is None:
                x_labels = details.get('x_labels', [])
            mean_gs = _compute_group_mean_grain_size(details['samples'], x_labels or [])
            self.group_stats[gid] = {
                'mean_grain_size': mean_gs,
                'count': details.get('count', len(details['samples']))
            }

        # Sort groups by mean grain size descending (coarsest first)
        self.sorted_groups = sorted(
            self.group_stats.keys(),
            key=lambda g: self.group_stats[g]['mean_grain_size'],
            reverse=True
        )

        self._setup_ui()
        self._set_default_mapping()
        self._validate()

    def _make_swatch_style(self, hex_color):
        """Return stylesheet for a color swatch button."""
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
            "Groups are shown sorted by mean grain size (coarsest first).\n"
            "Assign new label numbers using the dropdowns.\n"
            "Click the colour swatch to choose a custom colour."
        )
        header.setWordWrap(True)
        header.setStyleSheet("color: #333; font-size: 13px; padding: 5px;")
        layout.addWidget(header)

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

        # Form with one row per group
        form = QFormLayout()
        form.setSpacing(8)

        for gid in self.sorted_groups:
            stats = self.group_stats[gid]
            mean_gs = stats['mean_grain_size']
            count = stats['count']

            label_text = f"Original Group {gid}  —  mean: {mean_gs:.1f} μm, {count} samples"
            label = QLabel(label_text)
            label.setStyleSheet("font-size: 13px;")

            combo = QComboBox()
            combo.setFixedWidth(80)
            for i in range(1, self.k_value + 1):
                combo.addItem(str(i))
            combo.currentIndexChanged.connect(self._validate)
            combo.currentIndexChanged.connect(lambda idx, g=gid: self._update_row_swatch(g))
            self.combos[gid] = combo

            # Color swatch button for this row
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
            form.addRow(row_widget)

        layout.addLayout(form)

        # Warning label
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: #f44336; font-size: 12px; padding: 5px;")
        layout.addWidget(self.warning_label)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.setMinimumWidth(550)

    def _set_default_mapping(self):
        """Pre-assign labels: coarsest group -> 1, next -> 2, etc."""
        for rank, gid in enumerate(self.sorted_groups):
            self.combos[gid].setCurrentIndex(rank)  # rank 0 -> label "1"
        self._update_all_swatches()

    def _update_all_swatches(self):
        """Update all row color swatch buttons to reflect current colors."""
        for gid in self.combos:
            self._update_row_swatch(gid)

    def _update_row_swatch(self, gid):
        """Update the color swatch for a specific group row."""
        label_num = int(self.combos[gid].currentText())
        hex_color = self.colors.get(label_num, '#888888')
        self.color_buttons[gid].setStyleSheet(self._make_swatch_style(hex_color))

    def _update_legend(self):
        """Refresh legend buttons to reflect current colors."""
        for i, btn in self.legend_buttons.items():
            btn.setStyleSheet(
                f"background-color: {self.colors[i]}; color: white; "
                f"font-weight: bold; border-radius: 3px; padding: 2px 6px; border: 1px solid #666;"
            )

    def _pick_legend_color(self, label_num):
        """Open color picker for a legend label."""
        current = QColor(self.colors.get(label_num, '#888888'))
        color = QColorDialog.getColor(current, self, f"Choose colour for label {label_num}")
        if color.isValid():
            self.colors[label_num] = color.name()
            self._update_legend()
            self._update_all_swatches()

    def _pick_row_color(self, gid):
        """Open color picker for a specific group row."""
        label_num = int(self.combos[gid].currentText())
        current = QColor(self.colors.get(label_num, '#888888'))
        color = QColorDialog.getColor(current, self, f"Choose colour for label {label_num}")
        if color.isValid():
            self.colors[label_num] = color.name()
            self._update_legend()
            self._update_all_swatches()

    def _validate(self):
        """Check for duplicate label assignments."""
        values = []
        for gid, combo in self.combos.items():
            values.append(int(combo.currentText()))

        duplicates = len(values) != len(set(values))
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)

        if duplicates:
            self.warning_label.setText("⚠ Duplicate labels detected — each group must have a unique label.")
            ok_button.setEnabled(False)
            # Highlight duplicate combos
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
        """
        Return the relabel mapping.

        Returns:
            Dict {original_group_id: new_label} e.g. {0: 1, 1: 3, 2: 2}
        """
        mapping = {}
        for gid, combo in self.combos.items():
            mapping[gid] = int(combo.currentText())
        return mapping

    def get_colors(self):
        """
        Return the final color mapping.

        Returns:
            Dict {label: hex_color} e.g. {1: '#8B4513', 2: '#A0522D', ...}
        """
        return dict(self.colors)
