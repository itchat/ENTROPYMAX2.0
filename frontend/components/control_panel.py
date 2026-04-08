"""
Workflow-oriented control panel.
"""

from PyQt6.QtWidgets import (QWidget, QGroupBox, QVBoxLayout, QHBoxLayout,
                             QPushButton, QCheckBox, QLineEdit,
                             QLabel, QFileDialog, QToolButton, QMenu)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import pyqtSignal as Signal


class ControlPanel(QWidget):
    """Minimalist control panel following workflow steps."""

    # Signals
    inputFileSelected = Signal(str)
    gpsFileSelected = Signal(str)
    runAnalysisRequested = Signal(dict)  # Step 3: Run Analysis
    showMapRequested = Signal()  # Step 4: Show Map from Parquet
    exportResultsRequested = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.input_file = None
        self.gps_file = None
        self._setup_ui()
        self._update_button_states()
        
    def _setup_ui(self):
        """Initialize the minimalist UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Step 1: Input File
        input_group = QGroupBox("Step 1: Input Data")
        input_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                color: #333;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        input_layout = QVBoxLayout()
        input_layout.setContentsMargins(10, 15, 10, 10)
        
        self.select_input_btn = QPushButton("Select PSD CSV")
        self.select_input_btn.setStyleSheet("""
            QPushButton {
                background-color: #009688;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #00796b;
            }
            QPushButton:pressed {
                background-color: #004d40;
            }
        """)
        self.select_input_btn.clicked.connect(self._on_select_input)
        self.recent_input_btn = self._make_recent_button("Recent PSD")
        self.input_label = QLabel("No file selected")
        self.input_label.setStyleSheet("color: gray; padding: 5px;")

        # Add GPS file selection button
        self.select_gps_btn = QPushButton("Select GPS CSV")
        self.select_gps_btn.setStyleSheet("""
            QPushButton {
                background-color: #009688;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #00796b;
            }
            QPushButton:pressed {
                background-color: #004d40;
            }
        """)
        self.select_gps_btn.clicked.connect(self._on_select_gps)
        self.recent_gps_btn = self._make_recent_button("Recent GPS")
        self.gps_label = QLabel("No GPS file selected")
        self.gps_label.setStyleSheet("color: gray; padding: 5px;")

        # Horizontal rows: [Select button | Recent dropdown]
        psd_row = QHBoxLayout()
        psd_row.addWidget(self.select_input_btn, 1)
        psd_row.addWidget(self.recent_input_btn)
        gps_row = QHBoxLayout()
        gps_row.addWidget(self.select_gps_btn, 1)
        gps_row.addWidget(self.recent_gps_btn)

        input_layout.addLayout(psd_row)
        input_layout.addWidget(self.input_label)
        input_layout.addLayout(gps_row)
        input_layout.addWidget(self.gps_label)
        # Initialize empty placeholder menus
        self.setRecentInputs([])
        self.setRecentGps([])
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # Step 2: Analysis Parameters (renumbered from Step 3)
        params_group = QGroupBox("Step 2: Analysis Parameters")
        params_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                color: #333;
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
                background-color: white;
            }
        """)
        params_layout = QVBoxLayout()
        params_layout.setContentsMargins(10, 15, 10, 10)
        
        # Checkboxes
        checkbox_layout = QHBoxLayout()
        self.perm_check = QCheckBox("Permutations")
        self.perm_check.setChecked(True)
        self.perm_check.setStyleSheet("""
            QCheckBox { 
                font-size: 13px; 
                color: #333; 
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #d0d0d0;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #009688;
                background-color: #009688;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #4db6ac;
                background-color: #e0f2f1;
            }
        """)
        self.prop_check = QCheckBox("Row Proportions")
        self.prop_check.setStyleSheet("""
            QCheckBox { 
                font-size: 13px; 
                color: #333; 
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #d0d0d0;
                background-color: white;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #009688;
                background-color: #009688;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked:hover {
                border: 2px solid #4db6ac;
                background-color: #e0f2f1;
            }
        """)
        checkbox_layout.addWidget(self.perm_check)
        checkbox_layout.addWidget(self.prop_check)
        params_layout.addLayout(checkbox_layout)
        
        # Group range with minimalist design
        range_layout = QHBoxLayout()
        range_label = QLabel("Groups:")
        range_label.setStyleSheet("QLabel { font-size: 13px; color: #555; font-weight: 500; }")
        range_layout.addWidget(range_label)
        
        self.min_groups_input = QLineEdit()
        self.min_groups_input.setPlaceholderText("Min (2)")
        self.min_groups_input.setMaximumWidth(80)
        self.min_groups_input.setStyleSheet("""
            QLineEdit {
                background-color: #e0f2f1;
                border: 1px solid #009688;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
                color: #004d40;
            }
            QLineEdit:focus {
                border-color: #00796b;
                background-color: #ffffff;
            }
        """)
        
        self.max_groups_input = QLineEdit()
        self.max_groups_input.setPlaceholderText("Max (20)")
        self.max_groups_input.setMaximumWidth(80)
        self.max_groups_input.setStyleSheet("""
            QLineEdit {
                background-color: #e0f2f1;
                border: 1px solid #009688;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
                color: #004d40;
            }
            QLineEdit:focus {
                border-color: #00796b;
                background-color: #ffffff;
            }
        """)
        
        dash_label = QLabel("-")
        dash_label.setStyleSheet("QLabel { color: #666; font-size: 14px; }")
        
        range_layout.addWidget(self.min_groups_input)
        range_layout.addWidget(dash_label)
        range_layout.addWidget(self.max_groups_input)
        range_layout.addStretch()
        
        params_layout.addLayout(range_layout)
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)
        
        # Step 3: Run Analysis
        self.run_analysis_btn = QPushButton("Step 3: Run Analysis")
        self.run_analysis_btn.setEnabled(False)
        self.run_analysis_btn.clicked.connect(self._on_run_analysis)
        self.run_analysis_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #009688;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:enabled:hover {
                background-color: #00796b;
            }
            QPushButton:enabled:pressed {
                background-color: #004d40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        layout.addWidget(self.run_analysis_btn)
        
        # Step 4: Show Map View
        self.show_map_btn = QPushButton("Step 4: Update Map View")
        self.show_map_btn.setEnabled(False)
        self.show_map_btn.clicked.connect(self._on_show_map)
        self.show_map_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #009688;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:enabled:hover {
                background-color: #00796b;
            }
            QPushButton:enabled:pressed {
                background-color: #004d40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
                border: none;
                border-radius: 4px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
        """)
        layout.addWidget(self.show_map_btn)
        
        # Step 5: Export Results
        self.export_btn = QPushButton("Step 5: Export Results")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setStyleSheet("""
            QPushButton:enabled {
                background-color: #009688;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:enabled:hover {
                background-color: #00796b;
            }
            QPushButton:enabled:pressed {
                background-color: #004d40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        layout.addWidget(self.export_btn)
        
        layout.addStretch()
        
    def _make_recent_button(self, label: str) -> QToolButton:
        """Create a styled QToolButton with menu popup mode for recent files."""
        btn = QToolButton(self)
        btn.setText(" ▾ ")
        btn.setToolTip(label)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setStyleSheet("""
            QToolButton {
                background-color: #009688;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 6px;
                font-size: 13px;
                font-weight: 500;
                min-width: 28px;
            }
            QToolButton:hover {
                background-color: #00796b;
            }
            QToolButton::menu-indicator { image: none; }
        """)
        menu = QMenu(btn)
        btn.setMenu(menu)
        return btn

    def _populate_recent_menu(self, btn: QToolButton, entries: list, on_trigger):
        """Populate a recent-files menu, replacing existing actions."""
        menu = btn.menu()
        menu.clear()
        if not entries:
            placeholder = QAction("(no recent files)", self)
            placeholder.setEnabled(False)
            menu.addAction(placeholder)
            return
        for entry in entries:
            name = entry.get("name") or entry.get("path", "?")
            path = entry.get("path", "")
            action = QAction(name, self)
            action.setToolTip(path)
            action.setData(path)
            action.triggered.connect(lambda checked=False, p=path: on_trigger(p))
            menu.addAction(action)

    def setRecentInputs(self, entries: list) -> None:
        """Repopulate the recent PSD dropdown menu."""
        self._populate_recent_menu(
            self.recent_input_btn, entries or [], self._on_recent_input_selected
        )

    def setRecentGps(self, entries: list) -> None:
        """Repopulate the recent GPS dropdown menu."""
        self._populate_recent_menu(
            self.recent_gps_btn, entries or [], self._on_recent_gps_selected
        )

    def _on_recent_input_selected(self, path: str) -> None:
        """Handler when a recent PSD entry is clicked."""
        if not path:
            return
        self.input_file = path
        self.input_label.setText(f"✓ {path.split('/')[-1]}")
        self.input_label.setStyleSheet("color: green; padding: 5px;")
        self.inputFileSelected.emit(path)
        self._update_button_states()

    def _on_recent_gps_selected(self, path: str) -> None:
        """Handler when a recent GPS entry is clicked."""
        if not path:
            return
        self.gps_file = path
        self.gps_label.setText(f"✓ {path.split('/')[-1]}")
        self.gps_label.setStyleSheet("color: green; padding: 5px;")
        self.gpsFileSelected.emit(path)
        self._update_button_states()

    def populate_parameters(self, params: dict) -> None:
        """Set parameter widgets from a dict (reverse of get_analysis_parameters)."""
        if not isinstance(params, dict):
            return
        if "min_groups" in params:
            try:
                self.min_groups_input.setText(str(int(params["min_groups"])))
            except (ValueError, TypeError):
                pass
        if "max_groups" in params:
            try:
                self.max_groups_input.setText(str(int(params["max_groups"])))
            except (ValueError, TypeError):
                pass
        if "do_permutations" in params:
            self.perm_check.setChecked(bool(params["do_permutations"]))
        if "take_proportions" in params:
            self.prop_check.setChecked(bool(params["take_proportions"]))

    def _on_select_input(self):
        """Handle input file selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Grain Size CSV File", 
            "", 
            "CSV Files (*.csv)"
        )
        if file_path:
            self.input_file = file_path
            self.input_label.setText(f"✓ {file_path.split('/')[-1]}")
            self.input_label.setStyleSheet("color: green; padding: 5px;")
            self.inputFileSelected.emit(file_path)
            self._update_button_states()
    
    def _on_select_gps(self):
        """Handle GPS file selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select GPS CSV File", 
            "", 
            "CSV Files (*.csv)"
        )
        if file_path:
            self.gps_file = file_path
            self.gps_label.setText(f"✓ {file_path.split('/')[-1]}")
            self.gps_label.setStyleSheet("color: green; padding: 5px;")
            self.gpsFileSelected.emit(file_path)
            self._update_button_states()
            
    def _on_show_map(self):
        """Handle show map request."""
        self.showMapRequested.emit()
            
    def _on_run_analysis(self):
        """Handle run analysis request."""
        if self._validate_parameters():
            params = self.get_analysis_parameters()
            self.runAnalysisRequested.emit(params)
            # Note: Buttons will be enabled by main window after successful analysis
        
    def _on_export(self):
        """Handle export results request."""
        self.exportResultsRequested.emit()
        
    def _validate_parameters(self):
        """Validate group range parameters."""
        try:
            min_val = int(self.min_groups_input.text()) if self.min_groups_input.text() else 2
            max_val = int(self.max_groups_input.text()) if self.max_groups_input.text() else 20
            
            if min_val < 2 or max_val > 84 or min_val > max_val:
                return False
            return True
        except ValueError:
            return False
            
    def _update_button_states(self):
        """Update button states based on workflow progress."""
        # Enable run analysis when both input files are selected
        if self.input_file and self.gps_file:
            self.run_analysis_btn.setEnabled(True)
            
    def get_analysis_parameters(self):
        """Get current analysis parameters."""
        min_val = int(self.min_groups_input.text()) if self.min_groups_input.text() else 2
        max_val = int(self.max_groups_input.text()) if self.max_groups_input.text() else 20
        
        return {
            'min_groups': min_val,
            'max_groups': max_val,
            'do_permutations': self.perm_check.isChecked(),
            'take_proportions': self.prop_check.isChecked(),
            'input_file': self.input_file,
            'gps_file': self.gps_file
        }
        
    def enable_analysis(self):
        """Enable analysis button (called when samples are selected)."""
        self.run_analysis_btn.setEnabled(True)
    
    def enable_analysis_buttons(self, enabled=True):
        """Enable/disable analysis-related buttons."""
        self.export_btn.setEnabled(enabled)
        
    def reset_workflow(self):
        """Reset the entire workflow."""
        self.input_file = None
        self.gps_file = None
        self.input_label.setText("No file selected")
        self.input_label.setStyleSheet("color: gray; padding: 5px;")
        self.gps_label.setText("No GPS file selected")
        self.gps_label.setStyleSheet("color: gray; padding: 5px;")
        self.min_groups_input.clear()
        self.max_groups_input.clear()
        self.run_analysis_btn.setEnabled(False)
        self.show_map_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
