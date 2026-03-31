"""
Combines the map and sample list widgets together
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal as Signal
from .interactive_map_widget import InteractiveMapWidget
from .sample_list_widget import SampleListWidget


class SimpleMapSampleWidget(QWidget):
    """Simple map and sample list without fullscreen"""
    
    selectionChanged = Signal(list)
    sampleLocateRequested = Signal(str, float, float)
    sampleHovered = Signal(str)
    sampleUnhovered = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.markers_data = []
        self.selected_samples = []
        self._updating_from_map = False
        self._updating_from_list = False
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for map and list
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Map widget
        self.map_widget = InteractiveMapWidget()
        self.splitter.addWidget(self.map_widget)
        
        # Sample list
        self.sample_list = SampleListWidget()
        self.splitter.addWidget(self.sample_list)
        
        # Initial sizes
        self.splitter.setSizes([700, 500])
        layout.addWidget(self.splitter)
        
    def _connect_signals(self):
        """Connect signals for synchronization"""
        self.map_widget.selectionChanged.connect(self._on_map_selection_changed)
        self.sample_list.selectionChanged.connect(self._on_list_selection_changed)
        self.sample_list.sampleLocateRequested.connect(self._on_sample_locate_requested)
        self.map_widget.sampleHovered.connect(self.sampleHovered)
        self.map_widget.sampleUnhovered.connect(self.sampleUnhovered)
        
    def _on_map_selection_changed(self, selected_samples):
        """Handle map selection change"""
        if self._updating_from_list:
            return
            
        self._updating_from_map = True
        self.selected_samples = selected_samples
        
        # Update list with focus on last toggled
        if hasattr(self.map_widget, 'last_toggled_sample'):
            self.sample_list.set_selection_with_focus(
                selected_samples, 
                focus_sample=self.map_widget.last_toggled_sample
            )
            self.map_widget.last_toggled_sample = None
        else:
            self.sample_list.set_selection(selected_samples)
        
        self.selectionChanged.emit(selected_samples)
        self._updating_from_map = False
        
    def _on_list_selection_changed(self, selected_samples):
        """Handle list selection change"""
        if self._updating_from_map:
            return
            
        self._updating_from_list = True
        self.selected_samples = selected_samples
        self.map_widget.set_selection(selected_samples)
        self.selectionChanged.emit(selected_samples)
        self._updating_from_list = False
        
    def _on_sample_locate_requested(self, name, lat, lon):
        """Handle locate request"""
        self.map_widget.zoom_to_location(lat, lon, sample_name=name)
        self.sampleLocateRequested.emit(name, lat, lon)
        
    def load_data(self, markers_data, group_colors=None):
        """Load data into both widgets"""
        self.markers_data = markers_data
        self.map_widget.render_map(markers_data, group_colors=group_colors)
        self.sample_list.load_samples(markers_data)
        
    def get_selected_samples_data(self):
        """Get selected samples data"""
        return self.sample_list.get_selected_samples_data()
    
    def get_all_samples_data(self):
        """Get all samples data"""
        return self.markers_data
    
    def clear_selection(self):
        """Clear all selections"""
        self.selected_samples = []
        self.map_widget.clear_selection()
        self.sample_list.clear_all()