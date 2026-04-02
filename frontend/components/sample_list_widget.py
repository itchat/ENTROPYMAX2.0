"""
Sample list widget with checkboxes for selection and map navigation.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QPushButton, QLabel, QLineEdit)
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal as Signal
import shlex

# Parse query: free text, group, selected

def _parse_query(text: str):
    tokens = shlex.split(text)
    result = {
        "text": [],
        "groups": [],
        "selected": None,
    }

    def _parse_bool(v: str):
        s = v.lower()
        if s in ("true", "yes", "1", "on"):
            return True
        if s in ("false", "no", "0", "off"):
            return False
        return None

    for t in tokens:
        if ":" in t:
            key, val = t.split(":", 1)
            k = key.lower()
            v = val.strip()
            if k in ("group", "grp", "g"):
                if v:
                    result["groups"].append(v)
                continue
            if k in ("selected", "sel", "checked"):
                b = _parse_bool(v)
                if b is not None:
                    result["selected"] = b
                continue
        # otherwise treat as free text
        result["text"].append(t)

    result["text"] = " ".join(result["text"]).strip().lower()
    return result


class CustomSortTreeWidgetItem(QTreeWidgetItem):
    """Custom QTreeWidgetItem with sorting support for checkbox column."""
    
    def __lt__(self, other):
        """Custom comparison for sorting.
        
        Column 0 (checkbox): Checked items appear first
        Other columns: Default string/numeric comparison
        """
        column = self.treeWidget().sortColumn()
        
        if column == 0:  # Checkbox column
            # Get check states
            self_checked = self.checkState(0) == Qt.CheckState.Checked
            other_checked = other.checkState(0) == Qt.CheckState.Checked
            
            # If same state, maintain stable order
            if self_checked == other_checked:
                return False
            
            # Checked items should appear first (be "less than" unchecked)
            # Return True if self is unchecked and other is checked
            return not self_checked and other_checked
        
        if column == 2: # Number column
            key1 = self.text(2)
            key2 = other.text(2)
            try: 
                return float(key1) < float(key2)
            except ValueError:
                return key1 < key2
        
        # For other columns, use default comparison
        return super().__lt__(other)


class SampleListWidget(QWidget):
    """Widget for displaying and selecting samples with checkboxes."""
    
    # Signals
    selectionChanged = Signal(list)  # List of selected sample names
    sampleLocateRequested = Signal(str, float, float)  # name, lat, lon for map centering
    openPsdWindowRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples_data = []
        self.selected_samples = []
        self._setup_ui()
        self._apply_styles()
        
    def _setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Removed title label for cleaner interface
        search_layout = QHBoxLayout(self)
        search_layout.setSpacing(10)

        # Search input (minimal search bar)
        self.search_name_edit = QLineEdit()
        self.search_name_edit.setPlaceholderText("Search by name...")
        self.search_name_edit.setClearButtonEnabled(True)
        self.search_name_edit.textChanged.connect(self._filter_items)
        self.search_group_edit = QLineEdit()
        self.search_group_edit.setPlaceholderText("Search by group...")
        self.search_group_edit.setClearButtonEnabled(True)
        self.search_group_edit.textChanged.connect(self._filter_items)
        layout.addWidget(self.search_name_edit)
        layout.addWidget(self.search_group_edit)
        
        # Create tree widget for sample list
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(['✓', 'Sample Name', 'Group', 'Peak (μm)', 'Mean (μm)', 'Lat', 'Lon'])
        
        # Set column widths
        self.tree_widget.setColumnWidth(0, 40)  # Checkbox column
        self.tree_widget.setColumnWidth(1, 180)  # Name column
        self.tree_widget.setColumnWidth(2, 60)   # Group column
        self.tree_widget.setColumnWidth(3, 85)   # Lat column
        self.tree_widget.setColumnWidth(4, 85)   # Lon column
        
        # Enable sorting
        self.tree_widget.setSortingEnabled(True)
        self.tree_widget.setAlternatingRowColors(True)
        
        # Connect item click signal
        self.tree_widget.itemClicked.connect(self._on_item_clicked)
        self.tree_widget.itemChanged.connect(self._on_item_changed)
        
        layout.addWidget(self.tree_widget)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedHeight(32)
        self.select_all_btn.clicked.connect(self._select_all)
        
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.setFixedHeight(32)
        self.clear_all_btn.clicked.connect(self._clear_all)

        self.open_psd_btn = QPushButton("Plot Selected")
        self.open_psd_btn.setFixedHeight(32)
        self.open_psd_btn.clicked.connect(self._on_open_psd_clicked)    
    
        
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.clear_all_btn)
        button_layout.addWidget(self.open_psd_btn)
        layout.addLayout(button_layout)
        
        # Selection count label
        self.count_label = QLabel("Selected: 0 samples")
        self.count_label.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 13px;
                padding: 5px;
                background-color: #f5f5f5;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.count_label)
        
    def load_samples(self, samples_data):
        """
        Load samples into the list.
        
        Args:
            samples_data: List of dictionaries with 'name', 'lat', 'lon', 'group' keys
        """
        self.samples_data = samples_data
        self.tree_widget.clear()
        
        for sample in samples_data:
            item = CustomSortTreeWidgetItem()
            
            # Add checkbox in first column
            item.setCheckState(0, Qt.CheckState.Unchecked)
            
            # Sample name
            item.setText(1, sample.get('name', 'Unknown'))
            
            # Group
            group = sample.get('group', 0)
            item.setText(2, str(group))

            # Peak and Mean grain size
            peak = sample.get('peak_grain_size')
            mean = sample.get('mean_grain_size')
            item.setText(3, f"{peak:.1f}" if peak is not None else '')
            item.setText(4, f"{mean:.1f}" if mean is not None else '')

            # Coordinates
            item.setText(5, f"{sample.get('lat', 0):.4f}")
            item.setText(6, f"{sample.get('lon', 0):.4f}")

            # Store full sample data in item
            item.setData(1, Qt.ItemDataRole.UserRole, sample)

            self.tree_widget.addTopLevelItem(item)

        # Resize columns to content
        for i in range(7):
            self.tree_widget.resizeColumnToContents(i)
            
    def _on_item_clicked(self, item, column):
        """Handle item click - navigate to location on map if not checkbox."""
        if column != 0:  # Not checkbox column
            sample_data = item.data(1, Qt.ItemDataRole.UserRole)
            if sample_data:
                self.sampleLocateRequested.emit(
                    sample_data['name'],
                    sample_data['lat'],
                    sample_data['lon']
                )
                
    def _on_item_changed(self, item, column):
        """Handle checkbox state change."""
        if column == 0:  # Checkbox column
            self._update_selection()
            
    def _update_selection(self):
        """Update the list of selected samples."""
        self.selected_samples = []
        
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                sample_data = item.data(1, Qt.ItemDataRole.UserRole)
                if sample_data:
                    self.selected_samples.append(sample_data['name'])
        
        self.count_label.setText(f"Selected: {len(self.selected_samples)} samples")
        self.selectionChanged.emit(self.selected_samples)
        
    def _select_all(self):
        """Select all visible samples (respects search filter)."""
        # Temporarily disable sorting to avoid row reordering during iteration
        prev_sort = self.tree_widget.isSortingEnabled()
        if prev_sort:
            self.tree_widget.setSortingEnabled(False)
        
        # Block signals during batch update to prevent recursion
        self.tree_widget.blockSignals(True)
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            # Only select visible items (not hidden by search filter)
            if not item.isHidden():
                item.setCheckState(0, Qt.CheckState.Checked)
        self.tree_widget.blockSignals(False)
        
        # Restore sorting
        if prev_sort:
            self.tree_widget.setSortingEnabled(True)
        
        self._update_selection()
        
    def _clear_all(self):
        """Clear all visible selections (respects search filter)."""
        # Temporarily disable sorting to avoid row reordering during iteration
        prev_sort = self.tree_widget.isSortingEnabled()
        if prev_sort:
            self.tree_widget.setSortingEnabled(False)
        
        # Block signals during batch update to prevent recursion
        self.tree_widget.blockSignals(True)
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            # Only clear visible items (not hidden by search filter)
            if not item.isHidden():
                item.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree_widget.blockSignals(False)
        
        # Restore sorting
        if prev_sort:
            self.tree_widget.setSortingEnabled(True)
        
        self._update_selection()
    
    def _on_open_psd_clicked(self):
        """Emit signal to request opening PSD window."""
        self.openPsdWindowRequested.emit()
        
    def clear_all(self):
        """Public API to clear selection (external callers)."""
        self._clear_all()
        
    def get_selected_samples(self):
        """Return list of selected sample names."""
        return self.selected_samples
    
    def get_selected_samples_data(self):
        """Return full data for selected samples."""
        selected_data = []
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                sample_data = item.data(1, Qt.ItemDataRole.UserRole)
                if sample_data:
                    selected_data.append(sample_data)
        return selected_data
    
    def set_selection(self, sample_names, focus_last=False):
        """Set selection to specific samples and highlight them.
        
        Args:
            sample_names: List of sample names to select
            focus_last: If True, focus on the last changed item
        """
        first_selected_item = None
        last_changed_item = None
        
        # Temporarily disable sorting to avoid row reordering during iteration
        prev_sort = self.tree_widget.isSortingEnabled()
        if prev_sort:
            self.tree_widget.setSortingEnabled(False)
        
        # Block signals during batch update to prevent recursion
        self.tree_widget.blockSignals(True)
        
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            sample_data = item.data(1, Qt.ItemDataRole.UserRole)
            
            if sample_data:
                prev_state = item.checkState(0)
                
                if sample_data['name'] in sample_names:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    # Keep track of first selected item
                    if first_selected_item is None:
                        first_selected_item = item
                    # Track if this item's state changed
                    if prev_state != Qt.CheckState.Checked:
                        last_changed_item = item
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    # Track if this item's state changed
                    if prev_state == Qt.CheckState.Checked:
                        last_changed_item = item
        
        # Re-enable signals and restore sorting
        self.tree_widget.blockSignals(False)
        if prev_sort:
            self.tree_widget.setSortingEnabled(True)
        
        # Focus and scroll logic
        if focus_last and last_changed_item:
            # Focus on the last changed item (most recent selection/deselection)
            self.tree_widget.setCurrentItem(last_changed_item)
            self.tree_widget.scrollToItem(last_changed_item, QTreeWidget.ScrollHint.PositionAtCenter)
            # Give visual feedback by briefly highlighting
            self.tree_widget.setFocus()
        elif first_selected_item and len(sample_names) == 1:
            # For single selection, highlight and center it
            self.tree_widget.setCurrentItem(first_selected_item)
            self.tree_widget.scrollToItem(first_selected_item, QTreeWidget.ScrollHint.PositionAtCenter)
            self.tree_widget.setFocus()
        elif first_selected_item:
            # For multiple selection, ensure first is visible
            self.tree_widget.scrollToItem(first_selected_item, QTreeWidget.ScrollHint.EnsureVisible)
        
        self._update_selection()
    
    def set_selection_with_focus(self, sample_names, focus_sample=None):
        """Set selection and focus on a specific sample.
        
        Args:
            sample_names: List of all selected sample names
            focus_sample: The specific sample to focus on (last toggled)
        """
        # Update selection without triggering signals
        self.set_selection(sample_names, focus_last=False)
        
        # Focus on the specified sample if provided
        if focus_sample:
            for i in range(self.tree_widget.topLevelItemCount()):
                item = self.tree_widget.topLevelItem(i)
                sample_data = item.data(1, Qt.ItemDataRole.UserRole)
                if sample_data and sample_data['name'] == focus_sample:
                    self.tree_widget.setCurrentItem(item)
                    self.tree_widget.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)
                    self.tree_widget.setFocus()
                    break
    
    def highlight_sample(self, sample_name):
        """Highlight a specific sample in the list."""
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            sample_data = item.data(1, Qt.ItemDataRole.UserRole)
            if sample_data and sample_data['name'] == sample_name:
                self.tree_widget.setCurrentItem(item)
                self.tree_widget.scrollToItem(item, QTreeWidget.ScrollHint.PositionAtCenter)
                self.tree_widget.setFocus()
                break
    
    def _filter_items(self, text: str):
        """Filter by name and group from separate search boxes."""
        name_text = self.search_name_edit.text().strip().lower()
        group_text = self.search_group_edit.text().strip().lower()

        first_match = None
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            name = item.text(1).lower()
            group = item.text(2).lower()
            
            # Match both fields (AND)
            name_ok = not name_text or name_text in name
            group_ok = not group_text or group == group_text
            is_match = name_ok and group_ok
            
            item.setHidden(not is_match)
            
            if first_match is None and is_match:
                first_match = item

        if first_match:
            self.tree_widget.scrollToItem(first_match, QTreeWidget.ScrollHint.PositionAtTop)

    def _apply_styles(self):
        """Apply modern styling to the widget."""
        self.search_name_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px
                font-size: 13px;
                }
            QLineEdit:focus {
                border-color: #2196F3
                }
        """)
        self.search_group_edit.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px
                font-size: 13px;
                }
            QLineEdit:focus {
                border-color: #2196F3
                }
        """)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                font-size: 13px;
                outline: none;
                color: #000000;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #f5f5f5;
                color: #000000;
            }
            QTreeWidget::item:hover {
                background-color: #f8f9fa;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1976d2;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                color: #333;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #d0d0d0;
                border-right: 1px solid #e8e8e8;
                font-weight: 600;
                font-size: 13px;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QTreeWidget::item:alternate {
                background-color: #fafafa;
            }
            QTreeWidget::indicator {
                width: 16px;
                height: 16px;
            }
            QTreeWidget::indicator:unchecked {
                border: 2px solid #d0d0d0;
                background-color: white;
                border-radius: 3px;
            }
            QTreeWidget::indicator:checked {
                border: 2px solid #009688;
                background-color: #009688;
                border-radius: 3px;
                image: url(check.png);
            }
            QTreeWidget::indicator:unchecked:hover {
                border: 2px solid #4db6ac;
                background-color: #e0f2f1;
            }
        """)
        
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 15px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #2196F3;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 15px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #f44336;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)

        self.open_psd_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 6px 15px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #f44336;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
