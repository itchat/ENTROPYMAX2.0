import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QFrame, QMessageBox, QMenu, QFileDialog, QLabel)
from PyQt6.QtCore import Qt
from PyQt6 import QtGui
from components.control_panel import ControlPanel
from components.group_detail_popup import GroupDetailPopup
from components.module_preview_card import ModulePreviewCard
from components.standalone_window import StandaloneWindow
from components.simple_map_sample_widget import SimpleMapSampleWidget
from components.chart_widget import ChartWidget
from components.settings_dialog import SettingsDialog
from components.selected_psd_widget import SelectedPSDWidget
from help import FormatExamplesDialog, ValidationRulesDialog, UsageGuideDialog
from utils.create_kml import create_kml
from utils.recent_files import save_recent_files, load_recent_files
class BentoBox(QFrame):
    """A styled frame to create the bento box effect."""
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.title = title
        self.setStyleSheet("""
            BentoBox {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.setFrameShape(QFrame.Shape.NoFrame)


class EntropyMaxFinal(QMainWindow):
    """Main application with module preview cards."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EntropyMax2")
        basedir = os.path.dirname(__file__)
        self.setWindowIcon(QtGui.QIcon(os.path.join(basedir, 'emaxlight.ico')))
        self.setGeometry(100, 100, 1200, 700)
        self.setStyleSheet("""
            QMainWindow { 
                background-color: #f8f9fa; 
            }
            QStatusBar {
                background-color: #ffffff;
                border-top: 1px solid #e0e0e0;
                font-size: 12px;
                color: #666;
            }
        """)
        
        # State variables
        self.input_file_path = None
        self.gps_file_path = None
        self.selected_samples = []
        self.current_analysis_data = {}
        self.selected_k_for_details = None  # User-selected K value for group details
        self.group_relabel_mapping = {}  # {original_group: new_label}
        self.group_colors = {}  # {label: hex_color} from brown-yellow gradient
        self.group_detail_popup = GroupDetailPopup(main_window=self)
        
        # Initialize settings dialog
        self.settings_dialog = SettingsDialog(self)
        
        # Window references
        self.map_window = None
        self.ch_window = None
        self.rs_window = None
        self.selected_psd_window = None
        self._group_details_cache = {}
        
        self._setup_ui()
        self._setup_menu()
        self._init_standalone_windows()
        self._connect_signals()
        self._reset_workflow()
        
    def _setup_ui(self):
        """Initialize UI with preview cards."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # Left panel: Controls
        left_panel = BentoBox(title="Controls")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        self.control_panel = ControlPanel()
        left_layout.addWidget(self.control_panel)
        left_layout.addStretch()
        left_panel.setFixedWidth(340)
        main_layout.addWidget(left_panel)
        
        # Right panel: Module preview cards
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        rs_ch_row = QHBoxLayout()
        rs_ch_row.setSpacing(15)
        
        # RS analysis preview card
        self.rs_preview_card = ModulePreviewCard(
            title="Rs Analysis", 
            description="Rs Percentage visualization"
        )
        self.rs_preview_card.openRequested.connect(self._open_rs_window)
        rs_ch_row.addWidget(self.rs_preview_card)

        # CH analysis preview card
        self.ch_preview_card = ModulePreviewCard(
            title="CH Analysis",
            description="Calinski-Harabasz Index visualization"
        )
        self.ch_preview_card.openRequested.connect(self._open_ch_window)
        rs_ch_row.addWidget(self.ch_preview_card)
        
        right_layout.addLayout(rs_ch_row)
        # Map preview card
        self.map_preview_card = ModulePreviewCard(
            title="Map & Sample List",
            description="View GPS locations and manage sample selection"
        )
        self.map_preview_card.openRequested.connect(self._open_map_window)
        right_layout.addWidget(self.map_preview_card)
        
        # Selected PSD preview card
        self.selected_psd_preview_card = ModulePreviewCard(
            title="Selected PSD",
            description="Compare PSD curves for selected samples"
        )
        self.selected_psd_preview_card.openRequested.connect(self._open_selected_psd_window)
        right_layout.addWidget(self.selected_psd_preview_card)
        
        # Previously opened files banner moved to bottom
        self._add_recent_files_banner(right_layout)
        
        right_layout.addStretch()
        main_layout.addWidget(right_container)
    
    def _init_standalone_windows(self):
        """Initialize standalone window components"""
        # Map window with KML export enabled
        self.map_sample_widget = SimpleMapSampleWidget()
        self.map_window = StandaloneWindow("Map & Sample List", self.map_sample_widget, enable_kml_export=True)
        self.map_window.exportRequested.connect(lambda: self._export_window_content(self.map_sample_widget, "map"))
        self.map_window.exportKMLRequested.connect(self._on_export_kml)
        self.map_widget = self.map_sample_widget.map_widget
        self.sample_list = self.map_sample_widget.sample_list
        
        
        # CH chart window
        self.ch_chart = ChartWidget(
            title="CH Index",
            ylabel="CH Index"
        )
        self.ch_window = StandaloneWindow("CH Analysis", self.ch_chart)
        self.ch_window.exportRequested.connect(lambda: self._export_window_content(self.ch_chart, "ch"))
        
        # RS chart window
        self.rs_chart = ChartWidget(
            title="Rs %",
            ylabel="Rs %"
        )
        self.rs_window = StandaloneWindow("Rs Analysis", self.rs_chart)
        self.rs_window.exportRequested.connect(lambda: self._export_window_content(self.rs_chart, "rs"))
        
        # Selected PSD window
        self.selected_psd_widget = SelectedPSDWidget()
        self.selected_psd_window = StandaloneWindow("Selected PSD", self.selected_psd_widget)
        self.selected_psd_window.exportRequested.connect(lambda: self._export_window_content(self.selected_psd_widget, "selected_psd"))
        # Click a line/bar in Selected PSD -> focus sample in list (same as Group Details behavior)
        try:
            self.selected_psd_widget.lineClicked.connect(self._on_sample_line_clicked)
        except Exception:
            pass
    
    def _open_map_window(self):
        """Open map window"""
        if self.map_window:
            self.map_window.show()
            self.map_window.raise_()
            self.map_window.activateWindow()
    
    def _open_ch_window(self):
        """Open CH analysis window"""
        if self.ch_window:
            self.ch_window.show()
            self.ch_window.raise_()
            self.ch_window.activateWindow()
    
    def _open_rs_window(self):
        """Open RS analysis window"""
        if self.rs_window:
            self.rs_window.show()
            self.rs_window.raise_()
            self.rs_window.activateWindow()
    
    def _open_selected_psd_window(self):
        """Open Selected PSD window"""
        if self.selected_psd_window:
            self.selected_psd_window.show()
            self.selected_psd_window.raise_()
            self.selected_psd_window.activateWindow()
    
    def _export_window_content(self, widget, window_type):
        """Export window content as PNG"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {window_type.upper()} as PNG",
            f"{window_type}_export.png",
            "PNG Files (*.png)"
        )
        
        if file_path:
            pixmap = widget.grab()
            pixmap.save(file_path)
            self.statusBar().showMessage(f"Exported to {file_path}", 3000)
    
    def _setup_menu(self):
        """Setup the menu bar with Help menu."""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e0e0e0;
                padding: 5px;
            }
            QMenuBar::item {
                padding: 5px 10px;
                background: transparent;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #e0f2f1;
            }
            QMenuBar::item:pressed {
                background-color: #b2dfdb;
            }
        """)
        
        # Help menu
        help_menu = QMenu('Help', self)
        help_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 25px;
                background: transparent;
            }
            QMenu::item:selected {
                background-color: #e0f2f1;
            }
        """)
        
        # Add Format Examples action
        format_action = help_menu.addAction('Format Examples')
        format_action.triggered.connect(self._show_format_examples)

        # Add Validation Quick Rules action
        rules_action = help_menu.addAction('Validation Quick Rules')
        rules_action.triggered.connect(self._show_validation_rules)
        
        # Add Usage Guide  action
        usage_action = help_menu.addAction('Usage Guide')
        usage_action.triggered.connect(self._show_usage_guide)

        # Session menu with "Save & Exit" (shown to the left of Help on macOS)
        session_menu = QMenu('Session', self)
        session_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 25px;
                background: transparent;
            }
            QMenu::item:selected {
                background-color: #e0f2f1;
            }
        """)
        save_exit_action = session_menu.addAction('Save & Exit')
        save_exit_action.triggered.connect(self._on_save_and_exit)

        # Tools menu
        tools_menu = QMenu('Tools', self)
        tools_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 25px;
                background: transparent;
            }
            QMenu::item:selected {
                background-color: #e0f2f1;
            }
        """)
        self.relabel_action = tools_menu.addAction('Relabel Groups...')
        self.relabel_action.triggered.connect(self._on_relabel_groups)
        self.relabel_action.setEnabled(False)

        # View menu
        view_menu = QMenu('View', self)
        view_menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 8px 25px;
                background: transparent;
            }
            QMenu::item:selected {
                background-color: #e0f2f1;
            }
        """)
        self.always_on_top_action = view_menu.addAction('Always on Top')
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(False)
        self.always_on_top_action.triggered.connect(self._toggle_always_on_top)

        # Add menus to the menubar in order
        menubar.addMenu(session_menu)
        menubar.addMenu(view_menu)
        menubar.addMenu(tools_menu)
        menubar.addMenu(help_menu)

    def _toggle_always_on_top(self, checked):
        """Toggle always-on-top for the main control window."""
        if checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)
        self.show()

    def _show_format_examples(self):
        """Show dialog with format examples for CSV files."""
        dialog = FormatExamplesDialog(self)
        dialog.exec()

    def _show_validation_rules(self):
        """Show dialog with validation quick rules."""
        dialog = ValidationRulesDialog(self)
        dialog.exec()

    def _show_usage_guide(self):
        """Show user guide for how the steps work, with a user flow."""
        dialog = UsageGuideDialog(self)
        dialog.exec()
        
    def _on_save_and_exit(self):
        """Save names of opened data files and exit the application."""
        try:
            # Persist the current file selections (names and paths)
            save_recent_files(self.input_file_path, self.gps_file_path)
            self.statusBar().showMessage("Session saved. Exiting...", 2000)
        except Exception as e:
            # Non-fatal: still proceed to exit
            QMessageBox.warning(self, "Save & Exit", f"Failed to save recent files: {e}")
        finally:
            self.close()

    def _add_recent_files_banner(self, container_layout):
        """Render a small banner at the top showing previously opened files.
        Only displays when previous data exists.
        """
        data = load_recent_files()
        if not data:
            return
        input_info = data.get('input') or {}
        gps_info = data.get('gps') or {}
        saved_at = data.get('saved_at', '')

        # Build banner using card-like style (match ModulePreviewCard)
        banner = BentoBox(title="Previously Opened Files")
        banner.setObjectName("recentBanner")
        banner.setStyleSheet("""
            QFrame#recentBanner {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 15px;
            }
        """)
        v = QVBoxLayout(banner)
        # Match ModulePreviewCard: frame padding 15px + layout margins ~9px
        v.setContentsMargins(9, 9, 9, 9)
        v.setSpacing(6)

        title_label = QLabel("Previously Opened Data Files")
        title_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; color: #333; }")
        v.addWidget(title_label)

        # Minimal format: only full paths; names removed
        in_path = input_info.get('path') if input_info else None
        gps_path = gps_info.get('path') if gps_info else None

        lbl_in = QLabel(in_path or "(PSD: none)")
        lbl_in.setStyleSheet("QLabel { color: #666; font-size: 12px; }")
        lbl_in.setWordWrap(True)
        lbl_in.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl_in.setToolTip(in_path or "")
        v.addWidget(lbl_in)

        lbl_gps = QLabel(gps_path or "(GPS: none)")
        lbl_gps.setStyleSheet("QLabel { color: #666; font-size: 12px; }")
        lbl_gps.setWordWrap(True)
        lbl_gps.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl_gps.setToolTip(gps_path or "")
        v.addWidget(lbl_gps)

        if saved_at:
            # If stored in ISO, cut to seconds; otherwise show as-is
            pretty_time = saved_at.split(".")[0].replace("T", " ")
            lbl_time = QLabel(f"Saved at: {pretty_time}")
            lbl_time.setStyleSheet("QLabel { color: #999; font-size: 11px; }")
            v.addWidget(lbl_time)

        container_layout.addWidget(banner)
        
    def _connect_signals(self):
        """Connect all signals to their handlers."""
        self.control_panel.inputFileSelected.connect(self._on_input_file_selected)
        self.control_panel.gpsFileSelected.connect(self._on_gps_file_selected)
        self.control_panel.runAnalysisRequested.connect(self._on_run_analysis)
        self.control_panel.showMapRequested.connect(self._on_show_map)
        self.control_panel.exportResultsRequested.connect(self._on_export_results)
        
        # Connect signals from map-sample widget
        self.map_sample_widget.selectionChanged.connect(self._on_selection_changed)
        self.map_sample_widget.sampleLocateRequested.connect(self._on_locate_sample)
        self.sample_list.openPsdWindowRequested.connect(self._open_selected_psd_window)
        
        # Connect signal from group detail popup to sample list
        self.group_detail_popup.sampleLineClicked.connect(self._on_sample_line_clicked)
        
        # Cross-highlight: map <-> PSD curves
        self.map_sample_widget.sampleHovered.connect(self._on_map_sample_hovered)
        self.map_sample_widget.sampleUnhovered.connect(self._on_map_sample_unhovered)
        self.group_detail_popup.sampleHovered.connect(self._on_psd_sample_hovered)
        self.group_detail_popup.sampleUnhovered.connect(self._on_psd_sample_unhovered)
        self.selected_psd_widget.sampleHovered.connect(self._on_psd_sample_hovered)
        self.selected_psd_widget.sampleUnhovered.connect(self._on_psd_sample_unhovered)

        # Connect K value selection signals from charts - auto show group details
        self.rs_chart.kValueSelected.connect(self._on_k_value_selected_and_show_details)
        self.ch_chart.kValueSelected.connect(self._on_k_value_selected_and_show_details)
        
    def _on_input_file_selected(self, file_path):
        self.input_file_path = file_path
        # Validate raw data CSV format
        from utils.validate_csv_raw import validate_raw_data_csv
        
        valid, error_msg = validate_raw_data_csv(file_path)
        if valid:
            self.statusBar().showMessage("Raw data file loaded successfully")
        else:
            QMessageBox.warning(self, "Invalid Raw Data File", 
                              f"File validation failed:\n{error_msg}")
            self.input_file_path = None
            self.control_panel.input_file = None
            self.control_panel.input_label.setText("No file selected")
            self.control_panel.input_label.setStyleSheet("color: gray; padding: 5px;")
            self.control_panel._update_button_states()
    
    def _on_gps_file_selected(self, file_path):
        self.gps_file_path = file_path
        # Validate GPS CSV format
        from utils.validate_csv_gps import validate_gps_csv
        
        valid, error_msg = validate_gps_csv(file_path)
        if valid:
            self.statusBar().showMessage("GPS file loaded successfully.")
        else:
            QMessageBox.warning(self, "Invalid GPS File", 
                              f"File validation failed:\n{error_msg}")
            self.gps_file_path = None
            self.control_panel.gps_file = None
            self.control_panel.gps_label.setText("No GPS file selected")
            self.control_panel.gps_label.setStyleSheet("color: gray; padding: 5px;")
            self.control_panel._update_button_states()
        
    def _apply_map_for_k(self, k_value, announce=True):
        """
        Rebuild markers from analysis_data['gps_data'][k] and redraw the map.
        Preserves current sample selection.
        
        Args:
            k_value: K value to display
            announce: Whether to show status bar message
        """
        if not hasattr(self, 'current_analysis_data') or not self.current_analysis_data:
            QMessageBox.warning(self, "No Analysis Data", 
                              "Please run analysis first.")
            return
        
        gps_data_all = self.current_analysis_data.get('gps_data', {})
        gps_data = gps_data_all.get(int(k_value))
        
        if not gps_data:
            QMessageBox.warning(self, "No GPS Data", 
                              f"No GPS/group data found for K={k_value}.")
            return
        
        # Save current selection
        current_selection = list(self.selected_samples) if hasattr(self, 'selected_samples') else []
        
        # Convert to markers format, applying relabel mapping if active
        markers = []
        for sample_id, info in gps_data.items():
            group = info['group']
            if self.group_relabel_mapping:
                group = self.group_relabel_mapping.get(group, group)
            markers.append({
                'name': sample_id,
                'lat': info['lat'],
                'lon': info['lon'],
                'group': group,
                'selected': sample_id in current_selection
            })

        # Only pass custom colors if relabeling is active
        colors = self.group_colors if self.group_colors else None

        # Load map with grouped data
        self.map_sample_widget.load_data(markers, group_colors=colors)
        
        # Restore selection
        if current_selection:
            self.map_sample_widget.sample_list.set_selection(current_selection)
        
        # Update preview card
        self.map_preview_card.update_status(f"Loaded {len(markers)} samples (K={k_value})")
        
        if announce:
            self.statusBar().showMessage(f"Map updated for K={k_value}")
    
    def _on_show_map(self):
        """Load map data from Parquet and display."""
        try:
            if not hasattr(self, 'current_analysis_data') or not self.current_analysis_data:
                QMessageBox.warning(self, "No Analysis Data", 
                                  "Please run analysis first.")
                return
            
            k_values = self.current_analysis_data.get('k_values', [])
            
            # Prefer user-selected K; otherwise pick a K from the configured range (use max by default)
            k_to_show = None
            if hasattr(self, 'selected_k_for_details') and self.selected_k_for_details in k_values:
                k_to_show = int(self.selected_k_for_details)
            elif k_values:
                # Default to the max K within [min,max] range used in analysis
                k_to_show = int(max(k_values))
            
            if k_to_show is None:
                raise Exception("No valid K value to display on the map.")
            
            self._apply_map_for_k(k_to_show, announce=True)
            
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Map", str(e))
            
    def _on_selection_changed(self, selected_samples):
        self.selected_samples = selected_samples
        # Update Selected PSD view and card
        try:
            self._refresh_selected_psd()
            sel_count = len(self.selected_samples or [])
            self.selected_psd_preview_card.update_status(f"Selected: {sel_count} samples")
        except Exception:
            pass
        
    def _on_locate_sample(self, name, lat, lon):
        self.map_widget.zoom_to_location(lat, lon)
    

        
    def _on_sample_line_clicked(self, sample_name):
        """Handle sample line click from group detail popup."""
        # Just highlight the sample normally in the sample list
        self.sample_list.highlight_sample(sample_name)
        self.statusBar().showMessage(f"Highlighted sample: {sample_name}")

    def _on_map_sample_hovered(self, sample_name):
        """Map hover -> highlight in PSD curves (group detail + selected PSD)."""
        if getattr(self, '_hover_routing', False):
            return
        self._hover_routing = True
        self.group_detail_popup.highlight_sample(sample_name)
        self.selected_psd_widget.highlight_sample_externally(sample_name)
        self._hover_routing = False

    def _on_map_sample_unhovered(self):
        """Map hover leave -> clear PSD highlights."""
        if getattr(self, '_hover_routing', False):
            return
        self._hover_routing = True
        self.group_detail_popup.unhighlight_all()
        self.selected_psd_widget.unhighlight_externally()
        self._hover_routing = False

    def _on_psd_sample_hovered(self, sample_name):
        """PSD hover -> highlight on map."""
        if getattr(self, '_hover_routing', False):
            return
        self._hover_routing = True
        self.map_sample_widget.map_widget.highlight_marker(sample_name)
        self._hover_routing = False

    def _on_psd_sample_unhovered(self):
        """PSD hover leave -> clear map highlights."""
        if getattr(self, '_hover_routing', False):
            return
        self._hover_routing = True
        self.map_sample_widget.map_widget.unhighlight_all_markers()
        self._hover_routing = False

    def _on_k_value_selected_and_show_details(self, k_value):
        """Handle K value selection from charts and automatically show group details."""
        self.selected_k_for_details = int(k_value)
        # Reset relabel mapping when K changes
        self.group_relabel_mapping = {}
        self.group_colors = {}
        optimal_k = self.current_analysis_data.get('optimal_k', None)
        
        # Update status bar
        if k_value == optimal_k:
            self.statusBar().showMessage(
                f"Selected K={k_value} (Optimal). Loading details and updating map...", 
                
            )
        else:
            self.statusBar().showMessage(
                f"Selected K={k_value}. Loading details and updating map...", 
                
            )
        
        # 1) Show group details for selected K
        self._on_show_group_details()
        
        # 2) Update map grouping for selected K (refresh map if already loaded)
        try:
            self._apply_map_for_k(int(k_value), announce=False)
        except Exception as e:
            # Map may not be loaded yet, that's OK
            pass
        
        # 3) Refresh Selected PSD for new K
        try:
            self._refresh_selected_psd()
        except Exception:
            pass
        
    def _update_map_groups(self, gps_data):
        """Update map markers with group assignments from analysis"""
        # Get current markers
        current_markers = self.map_sample_widget.get_all_samples_data()
        
        # Update group assignments based on analysis results
        updated_markers = []
        for marker in current_markers:
            sample_name = marker['name']
            if sample_name in gps_data:
                marker['group'] = gps_data[sample_name]['group']
            updated_markers.append(marker)
        
        # Reload map with updated groups
        self.map_sample_widget.load_data(updated_markers)
        
    def _on_run_analysis(self, params):
        """Run analysis using real CLI"""
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        from utils.temp_manager import TempFileManager
        from utils.cli_integration import CLIIntegration
        from utils.data_pipeline import DataPipeline
        
        # Cross-check sample names between Raw and GPS before heavy work
        try:
            only_in_raw, only_in_gps = self._cross_check_sample_names(params.get('input_file'), params.get('gps_file'))
            if only_in_raw or only_in_gps:
                # Build short warning text
                def _fmt_list(xs, n=10):
                    xs = list(xs)
                    if not xs:
                        return "None"
                    if len(xs) > n:
                        return ", ".join(xs[:n]) + f" … (+{len(xs)-n} more)"
                    return ", ".join(xs)
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Sample name mismatch")
                msg.setText("Raw CSV and GPS CSV have different sample names.")
                info_lines = [
                    f"Only in Raw: {len(only_in_raw)}",
                    _fmt_list(sorted(only_in_raw)),
                    f"Only in GPS: {len(only_in_gps)}",
                    _fmt_list(sorted(only_in_gps)),
                    "\nContinue anyway? This may cause unknown errors later."
                ]
                msg.setInformativeText("\n".join(info_lines))
                # Use explicit buttons to avoid platform quirks
                continue_btn = msg.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
                cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                msg.setDefaultButton(cancel_btn)
                msg.exec()
                if msg.clickedButton() is not continue_btn:
                    return
        except Exception:
            # Non-fatal; proceed
            pass
        
        # Initialize managers
        self.temp_manager = TempFileManager()
        
        try:
            # Setup binary from bundle (always copy to ensure integrity)
            try:
                binary_path = self.temp_manager.setup_binary_from_bundle()
            except Exception as e:
                raise Exception(f"Failed to setup CLI binary: {e}")
            
            cli = CLIIntegration(cli_path=binary_path)
            pipeline = DataPipeline()
            
            # Show progress dialog
            progress = QProgressDialog("Running analysis...", None, 0, 5, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            # Step 1: Setup binary
            progress.setLabelText("Preparing analysis environment...")
            progress.setValue(1)
            QApplication.processEvents()
            
            # Step 2: Run CLI
            progress.setLabelText("Running EntropyMax analysis...")
            progress.setValue(2)
            QApplication.processEvents()
            
            output_csv = str(self.temp_manager.get_path('cli_output'))
            success, message = cli.run_analysis(
                params['input_file'],
                params['gps_file'], 
                output_csv,
                params,
                working_dir=str(self.temp_manager.session_dir)
            )
            
            if not success:
                raise Exception(f"CLI failed: {message}")
                
            # Step 3: Convert to Parquet
            progress.setLabelText("Converting to Parquet format...")
            progress.setValue(3)
            QApplication.processEvents()
            
            parquet_path = str(self.temp_manager.get_path('parquet'))
            if not pipeline.csv_to_parquet(output_csv, parquet_path):
                raise Exception("Failed to convert CSV to Parquet")
                
            # Step 4: Extract data
            progress.setLabelText("Extracting analysis results...")
            progress.setValue(4)
            QApplication.processEvents()
            
            analysis_data = pipeline.extract_analysis_data(parquet_path)
            if not analysis_data:
                raise Exception("Failed to extract data from Parquet")
                
            # Step 5: Update UI
            progress.setLabelText("Updating visualizations...")
            progress.setValue(5)
            QApplication.processEvents()
            
            # Save analysis data
            optimal_k = analysis_data.get('optimal_k')
            self.current_analysis_data = {
                **params,
                **analysis_data,
                'parquet_path': parquet_path
            }
            # reset group details cache on new run
            self._group_details_cache = {}
            
            # Plot results
            self._plot_analysis_results()
            
            # Update status (don't update map yet, wait for Step 4)
            self.ch_preview_card.update_status("Analysis complete")
            self.rs_preview_card.update_status("Analysis complete")
            self.map_preview_card.update_status("Ready - Click 'Update Map View' to display results")
            
            # Enable next step buttons
            self.control_panel.show_map_btn.setEnabled(True)
            self.control_panel.export_btn.setEnabled(True)
            
            progress.close()
            self.relabel_action.setEnabled(True)
            self.group_relabel_mapping = {}
            self.group_colors = {}
            self.statusBar().showMessage(f"Analysis complete. Optimal K={optimal_k}. Click 'Update Map View' to see results")
            
        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(self, "Analysis Error", str(e))
            self.statusBar().showMessage("Analysis failed.")
            # Cleanup on error
            if hasattr(self, 'temp_manager'):
                self.temp_manager.cleanup()
        
    def _on_show_group_details(self):
        """Show group detail popups with line charts for each group."""
        if not hasattr(self, 'current_analysis_data') or not self.current_analysis_data:
            QMessageBox.warning(self, "No Analysis Data", 
                              "Please run analysis first.")
            return
        
        try:
            from utils.data_pipeline import DataPipeline
            
            # Use user-selected K if available; otherwise prefer optimal K when valid; else fall back to max available K
            k_values = self.current_analysis_data.get('k_values', [])
            optimal_k = self.current_analysis_data.get('optimal_k', None)
            if self.selected_k_for_details is not None and (not k_values or int(self.selected_k_for_details) in k_values):
                k_value = int(self.selected_k_for_details)
            elif k_values:
                k_value = int(max(k_values))  # default to highest K (e.g., 20)
            elif optimal_k is not None:
                k_value = int(optimal_k)
            else:
                raise Exception("No available K values in analysis data")
            
            parquet_path = self.current_analysis_data.get('parquet_path')
            
            if not parquet_path:
                raise Exception("Parquet file path not found in analysis data")
            
            # Extract group details from Parquet
            pipeline = DataPipeline()
            group_details = pipeline.extract_group_details(parquet_path, k_value)
            
            if not group_details:
                raise Exception(f"No group data found for K={k_value}")

            # Apply relabel mapping if active
            if self.group_relabel_mapping:
                relabeled = {}
                for gid, details in group_details.items():
                    new_gid = self.group_relabel_mapping.get(gid, gid)
                    relabeled[new_gid] = details
                group_details = relabeled

            # Only pass custom colors if relabeling is active
            colors = self.group_colors if self.group_colors else None

            # Show group detail popups with extracted data
            self.group_detail_popup.load_and_show_popups_from_data(
                group_details, k_value, x_unit='μm', y_unit='%', group_colors=colors
            )
            
            optimal_k = self.current_analysis_data.get('optimal_k', None)
            if k_value == optimal_k:
                self.statusBar().showMessage(f"Showing details for K={k_value} groups (Optimal).")
            else:
                self.statusBar().showMessage(f"Showing details for K={k_value} groups.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error Showing Group Details", str(e))
    
    def _on_relabel_groups(self):
        """Open the relabel groups dialog."""
        if not hasattr(self, 'current_analysis_data') or not self.current_analysis_data:
            QMessageBox.warning(self, "No Analysis Data",
                              "Please run analysis first.")
            return

        from components.relabel_groups_dialog import RelabelGroupsDialog
        from utils.data_pipeline import DataPipeline

        k_values = self.current_analysis_data.get('k_values', [])
        k_value = getattr(self, 'selected_k_for_details', None)
        if k_value is None or k_value not in k_values:
            if k_values:
                k_value = int(max(k_values))
            else:
                QMessageBox.warning(self, "No K Value", "No K values available.")
                return

        parquet_path = self.current_analysis_data.get('parquet_path')
        if not parquet_path:
            QMessageBox.warning(self, "Error", "Parquet file not found.")
            return

        pipeline = DataPipeline()
        group_details = pipeline.extract_group_details(parquet_path, int(k_value))
        if not group_details:
            QMessageBox.warning(self, "Error", f"No group data for K={k_value}.")
            return

        dialog = RelabelGroupsDialog(group_details, int(k_value), parent=self)
        if dialog.exec():
            self.group_relabel_mapping = dialog.get_mapping()
            self.group_colors = dialog.get_colors()

            # Refresh map and group details
            try:
                self._apply_map_for_k(int(k_value), announce=False)
            except Exception:
                pass
            try:
                self._on_show_group_details()
            except Exception:
                pass

            self.statusBar().showMessage(f"Groups relabeled for K={k_value}")

    @staticmethod
    def _default_kml_colors(k_value):
        """Generate default colors for KML export when no relabel colors are set."""
        palette = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#FFD93D', '#6C5CE7', '#FD79A8',
        ]
        return {i + 1: palette[i % len(palette)] for i in range(int(k_value))}

    def _on_export_results(self):
        """Export analysis results CSV and cleanup temp files."""
        if not self.current_analysis_data:
            QMessageBox.warning(self, "No Results", 
                              "Please run an analysis first.")
            return
        
        if not hasattr(self, 'temp_manager'):
            QMessageBox.warning(self, "No Temp Files", 
                              "No temporary files found to export.")
            return
        
        # Let user choose output file location
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Export Analysis Results", 
            "analysis_results.csv", 
            "CSV Files (*.csv)"
        )
        
        if not file_path:  # User cancelled
            return
        
        try:
            from pathlib import Path
            
            # Ensure .csv extension
            if not file_path.endswith('.csv'):
                file_path += '.csv'
            
            # Export the processed CSV from temp directory
            self.temp_manager.export_to('cli_output', Path(file_path))
            
            # Clean up temporary files after successful export
            self.temp_manager.cleanup()
            
            QMessageBox.information(self, "Export Successful", 
                                f"Results saved to:\n{file_path}\n\nTemporary files have been cleaned up.")
            
            self.statusBar().showMessage(f"Results exported to {Path(file_path).name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", 
                              f"Failed to export results:\n{str(e)}")
    
    def _on_export_kml(self):
        """Export map data as KML file using teammate's implementation."""
        if not self.current_analysis_data:
            QMessageBox.warning(self, "No Results", 
                              "Please run analysis first before exporting KML.")
            return
        
        from PyQt6.QtWidgets import QInputDialog, QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
        
        # Get parquet path from analysis data
        parquet_path = self.current_analysis_data.get('parquet_path')
        if not parquet_path:
            QMessageBox.critical(self, "KML Export Error", 
                              "Parquet file path not found in analysis data.")
            return
        
        # Get available K values
        k_values = self.current_analysis_data.get('k_values', [])
        optimal_k = self.current_analysis_data.get('optimal_k')
        
        if not k_values:
            QMessageBox.critical(self, "KML Export Error", 
                              "No K values found in analysis data.")
            return
        
        # Step 1: Ask user for K value (default to selected K when available, otherwise optimal K)
        selected_k = getattr(self, 'selected_k_for_details', None)
        if isinstance(selected_k, (int, float)) and selected_k in k_values:
            default_k = int(selected_k)
        elif isinstance(optimal_k, (int, float)) and optimal_k in k_values:
            default_k = int(optimal_k)
        else:
            default_k = int(max(k_values))
        
        prompt_opt_text = f", Optimal: {optimal_k}" if (isinstance(optimal_k, (int, float)) and optimal_k in k_values) else ""
        k_value, ok = QInputDialog.getInt(
            self,
            "Select Group Number",
            f"Enter number of groups:\n(Available: {min(k_values)}-{max(k_values)}{prompt_opt_text})",
            default_k,  # default value
            min(k_values),  # minimum
            max(k_values),  # maximum
            1  # step
        )
        
        if not ok:
            return
        
        # Validate K value
        if k_value not in k_values:
            QMessageBox.warning(self, "Invalid K Value", 
                              f"K={k_value} is not in the analysis results.\nAvailable values: {k_values}")
            return
        
        # Step 2: Ask user to choose: All groups or specific group (use actual group ids from analysis data)
        try:
            group_map = self.current_analysis_data.get('groupings', {}).get(int(k_value), {})
            actual_groups = sorted(int(gid) for gid in group_map.keys()) if group_map else []
        except Exception:
            actual_groups = []
        
        group_options = ["All groups separate"]
        if actual_groups:
            for gid in actual_groups:
                display_gid = self.group_relabel_mapping.get(gid, gid) if self.group_relabel_mapping else gid
                group_options.append(f"Group {display_gid} only")
        else:
            for i in range(1, k_value + 1):
                group_options.append(f"Group {i} only")
        group_options.append("All individual data points")
        
        group_choice, ok = QInputDialog.getItem(
            self,
            "Select Groups to Export",
            f"Choose which group(s) to export for K={k_value}:",
            group_options,
            0,  # default to "All groups"
            False  # not editable
        )
        
        if not ok:
            return
        
        # Parse group choice (0 = all, 1-k = specific group)
        if group_choice == "All groups separate":
            if actual_groups:
                groups_to_export = actual_groups
            else:
                groups_to_export = list(range(1, k_value + 1))
            for group_number in groups_to_export:
                filename_suffix = f"k{k_value}_group{group_number}"
                file_path, _ = QFileDialog.getSaveFileName(
                    self, 
                    f"Export KML for Group {group_number}",
                    f"map_{filename_suffix}.kml",
                    "KML Files (*.kml)"
                )
                if not file_path:
                    continue
                if not file_path.endswith('.kml'):
                    file_path += '.kml'
                try:
                    create_kml(parquet_path, k_value, group_number, file_path.replace('.kml', ''), relabel_mapping=self.group_relabel_mapping or None, group_colors=self.group_colors or self._default_kml_colors(k_value))
                except Exception as e:
                    QMessageBox.critical(self, "KML Export Error", f"Failed to export KML for group {group_number};\n{str(e)}")
            self.statusBar().showMessage(f"KML exported: K = {k_value}, all groups separately")
            return
        if group_choice == "All individual data points":
            group_number = 0
            filename_suffix = f"k{k_value}_all"
            export_description = "All individual data points"
        else:
            group_number = int(group_choice.split()[1])  # Extract number from "Group X only"
            filename_suffix = f"k{k_value}_group{group_number}"
            export_description = f"Group {group_number} only"
        
        # Step 3: Let user choose output file location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export KML File",
            f"map_{filename_suffix}.kml",
            "KML Files (*.kml)"
        )
        
        if not file_path:  # User cancelled
            return
        
        try:
            # Ensure .kml extension
            if not file_path.endswith('.kml'):
                file_path += '.kml'
            
            # Use teammate's create_kml function with group_number parameter
            # Parameters: file_name (parquet), k_value, group_number (0 = all groups), output_file_name
            create_kml(parquet_path, k_value, group_number, file_path.replace('.kml', ''), relabel_mapping=self.group_relabel_mapping or None, group_colors=self.group_colors or self._default_kml_colors(k_value))

            QMessageBox.information(self, "Export Successful", 
                                f"KML file exported successfully:\n{file_path}\n\nK-value: {k_value}\n{export_description}")
            
            self.statusBar().showMessage(f"KML exported: K={k_value}, {export_description}")
            
        except Exception as e:
            QMessageBox.critical(self, "KML Export Error", 
                              f"Failed to export KML:\n{str(e)}")
            
    def _plot_analysis_results(self):
        """Plot the analysis results."""
        k_values = self.current_analysis_data['k_values']
        ch_values = self.current_analysis_data['ch_values']
        rs_values = self.current_analysis_data['rs_values']
        optimal_k = self.current_analysis_data['optimal_k']
        
        self.ch_chart.plot_data(k_values, ch_values, '#2196F3', 'o', 'CH Index')  # Blue
        self.rs_chart.plot_data(k_values, rs_values, '#4CAF50', 's', 'Rs %')  # Green
        # self.group_graph_widget.plot_analysis_results(x_values, group_values, peak_k)
        # self.group_graph_widget.plot_analysis_results(x_values, group_values)
        
        if optimal_k is not None:
            idx = list(k_values).index(optimal_k)
            self.ch_chart.add_optimal_marker(optimal_k, ch_values[idx])
        
        # Also refresh Selected PSD (will be empty if no selection yet)
        try:
            self._refresh_selected_psd()
        except Exception:
            pass
            
    def _reset_workflow(self):
        """Reset the UI to its initial state."""
        # Clean up temp files if they exist
        if hasattr(self, 'temp_manager'):
            try:
                self.temp_manager.cleanup()
            except Exception as e:
                print(f"Warning: Failed to cleanup temp files: {e}")
        
        # Reset file paths
        self.input_file_path = None
        self.gps_file_path = None
        self.selected_samples = []
        self.selected_k_for_details = None
        
        # Reset UI components
        self.control_panel.reset_workflow()
        self.map_sample_widget.load_data([])
        self.ch_chart.clear()
        self.rs_chart.clear()
        if hasattr(self, 'selected_psd_widget'):
            self.selected_psd_widget.clear()
        self.group_detail_popup.close_all()
        self.current_analysis_data = {}
        self._group_details_cache = {}
        
        # Reset preview cards
        self.map_preview_card.update_status("Not loaded")
        self.ch_preview_card.update_status("Not loaded")
        self.rs_preview_card.update_status("Not loaded")
        if hasattr(self, 'selected_psd_preview_card'):
            self.selected_psd_preview_card.update_status("Not loaded")
        
        self.statusBar().showMessage("Workflow reset. Select input files to begin.")
    
    def closeEvent(self, event):
        """Handle window close event and cleanup entire cache directory."""
        from utils.temp_manager import TempFileManager
        
        # Close all group detail popups before closing the main window
        self.group_detail_popup.close_all()
        
        # Clean up cache directory contents on app exit
        try:
            TempFileManager.cleanup_entire_cache()
            print("Cache directory contents cleaned up on exit")
        except Exception as e:
            print(f"Warning: Failed to cleanup cache directory on exit: {e}")
        
        super().closeEvent(event)


    def _get_group_details_for_k(self, k_value):
        """Load group details for K with simple cache."""
        if not self.current_analysis_data:
            return None
        k = int(k_value)
        if k in self._group_details_cache:
            return self._group_details_cache[k]
        parquet_path = self.current_analysis_data.get('parquet_path')
        if not parquet_path:
            return None
        try:
            from utils.data_pipeline import DataPipeline
            pipeline = DataPipeline()
            details = pipeline.extract_group_details(parquet_path, k)
            if details:
                self._group_details_cache[k] = details
            return details
        except Exception:
            return None

    def _refresh_selected_psd(self):
        """Update Selected PSD widget based on current selection and K."""
        if not hasattr(self, 'selected_psd_widget'):
            return
        if not self.current_analysis_data:
            self.selected_psd_widget.clear()
            return
        selected = list(self.selected_samples) if hasattr(self, 'selected_samples') else []
        if not selected:
            self.selected_psd_widget.clear()
            return
        # decide K
        if self.selected_k_for_details is not None:
            k_value = int(self.selected_k_for_details)
        else:
            k_value = int(self.current_analysis_data.get('optimal_k')) if self.current_analysis_data.get('optimal_k') is not None else None
        if k_value is None:
            self.selected_psd_widget.clear()
            return
        group_details = self._get_group_details_for_k(k_value)
        if not group_details:
            self.selected_psd_widget.clear()
            return
        # collect x_labels and sample curves
        x_labels = None
        samples_to_plot = []
        # take x_labels from the first group that exists
        for gid in sorted(group_details.keys()):
            if not x_labels:
                x_labels = group_details[gid].get('x_labels')
            # search for selected samples in this group
            for s in group_details[gid].get('samples', []):
                if s.get('name') in selected:
                    samples_to_plot.append({'name': s.get('name'), 'values': s.get('values')})
        if not samples_to_plot or not x_labels:
            self.selected_psd_widget.clear()
            return
        self.selected_psd_widget.update_curves(x_labels, samples_to_plot)

    def _cross_check_sample_names(self, raw_csv: str, gps_csv: str):
        """Return (only_in_raw, only_in_gps) sets. Case-sensitive; trims spaces."""
        try:
            import pandas as pd
            df_raw = pd.read_csv(raw_csv, low_memory=False)
            df_gps = pd.read_csv(gps_csv, low_memory=False)
            raw_names = df_raw['Sample Name'].astype(str).str.strip()
            gps_names = df_gps['Sample Name'].astype(str).str.strip()
            set_raw = set(raw_names.tolist())
            set_gps = set(gps_names.tolist())
            return set_raw - set_gps, set_gps - set_raw
        except Exception:
            return set(), set()

if __name__ == '__main__':
    # Fix fractional DPI scaling on Windows (125%, 150%) — must be before QApplication
    os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    basedir = os.path.dirname(__file__)
    app.setWindowIcon(QtGui.QIcon(os.path.join(basedir, 'emaxlight.ico')))
    app.setStyle('Fusion')
    window = EntropyMaxFinal()
    window.show()
    sys.exit(app.exec())
