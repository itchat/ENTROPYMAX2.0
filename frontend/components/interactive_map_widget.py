"""
Enhanced interactive map widget with direct point selection and group visualization.
"""

import folium
from statistics import mean
from PyQt6.QtCore import QUrl
from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from utils.cache_paths import ensure_cache_subdir
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import json


class MapBridge(QObject):
    """Bridge for communication between Python and JavaScript."""

    # Signals for Python to JavaScript
    selectionChanged = Signal(list)  # Emitted when selection changes in Python

    # Signals for JavaScript to Python
    markerClicked = Signal(str)  # Sample name when marker is clicked
    markersSelected = Signal(list)  # List of sample names selected
    boxSelectionComplete = Signal(list)  # List of sample names in box selection
    singleMarkerToggled = Signal(str, bool)  # Sample name and new state
    markerHovered = Signal(str)  # Sample name on hover enter
    markerUnhovered = Signal()  # Hover leave

    def __init__(self):
        super().__init__()
        self.selected_samples = []

    @pyqtSlot(str)
    def onMarkerClick(self, sample_name):
        """Handle marker click from JavaScript."""
        self.markerClicked.emit(sample_name)

    @pyqtSlot(str)
    def onBoxSelection(self, samples_json):
        """Handle box selection from JavaScript."""
        try:
            samples = json.loads(samples_json)
            self.boxSelectionComplete.emit(samples)
        except:
            pass

    @pyqtSlot(str)
    def onMultiSelection(self, samples_json):
        """Handle multiple selection with Ctrl/Shift from JavaScript."""
        try:
            samples = json.loads(samples_json)
            self.markersSelected.emit(samples)
        except:
            pass

    @pyqtSlot(str)
    def onMarkerHover(self, sample_name):
        """Handle marker hover enter from JavaScript."""
        self.markerHovered.emit(sample_name)

    @pyqtSlot()
    def onMarkerUnhover(self):
        """Handle marker hover leave from JavaScript."""
        self.markerUnhovered.emit()

    def updateSelection(self, selected_samples):
        """Update selection from Python side."""
        self.selected_samples = selected_samples
        self.selectionChanged.emit(selected_samples)


class InteractiveMapWidget(QWidget):
    """Enhanced map widget with direct point selection and group visualization."""
    
    # Signal emitted when samples are selected/deselected
    selectionChanged = Signal(list)  # list of selected sample names
    sampleHovered = Signal(str)  # emitted when mouse enters a marker
    sampleUnhovered = Signal()  # emitted when mouse leaves a marker
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_samples = []
        self.markers_data = []
        self.group_colors = None
        self.last_toggled_sample = None
        self.bridge = MapBridge()
        self._setup_ui()
        self._connect_bridge_signals()
        
    def _get_map_html_path(self):
        """Get the path for map HTML file in entro_cache/cache directory."""
        cache_dir = ensure_cache_subdir("cache")
        return str(cache_dir / "interactive_map.html")
    
    def _setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Create web view for map
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(300)
        
        # Create custom page with web channel
        self.page = QWebEnginePage()
        self.channel = QWebChannel()
        self.channel.registerObject("mapBridge", self.bridge)
        self.page.setWebChannel(self.channel)
        self.web_view.setPage(self.page)
        
        # Configure web engine settings
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        
        layout.addWidget(self.web_view)
        
    def _connect_bridge_signals(self):
        """Connect bridge signals for bidirectional communication."""
        self.bridge.markerClicked.connect(self._on_marker_clicked)
        self.bridge.boxSelectionComplete.connect(self._on_box_selection)
        self.bridge.markersSelected.connect(self._on_multi_selection)
        self.bridge.markerHovered.connect(self.sampleHovered)
        self.bridge.markerUnhovered.connect(self.sampleUnhovered)
        
    def _on_marker_clicked(self, sample_name):
        """Handle single marker click."""
        was_selected = sample_name in self.selected_samples
        
        if was_selected:
            self.selected_samples.remove(sample_name)
        else:
            self.selected_samples.append(sample_name)
        
        # Track the last toggled sample for focus
        self.last_toggled_sample = sample_name
        
        self.selectionChanged.emit(self.selected_samples)
        self.bridge.updateSelection(self.selected_samples)
        
    def _on_box_selection(self, sample_names):
        """Handle box selection."""
        # Add all samples in box to selection
        for name in sample_names:
            if name not in self.selected_samples:
                self.selected_samples.append(name)
        
        self.selectionChanged.emit(self.selected_samples)
        self.bridge.updateSelection(self.selected_samples)
        
    def _on_multi_selection(self, sample_names):
        """Handle multi-selection with Ctrl/Shift."""
        self.selected_samples = sample_names
        self.selectionChanged.emit(self.selected_samples)
        
    def render_map(self, markers_data, center=None, zoom=None, group_colors=None):
        """
        Render the interactive map with enhanced selection capabilities.

        Args:
            markers_data: List of dictionaries with 'lat', 'lon', 'name', 'group' keys
            center: Optional tuple (lat, lon) to center the map
            zoom: Optional zoom level
            group_colors: Optional dict {group_number: hex_color}. If None, uses brown-yellow gradient.
        """
        self.markers_data = markers_data
        if group_colors is not None:
            self.group_colors = group_colors

        if center is None:
            if not markers_data:
                center = (-25.0, 133.0)  # Australia center
            else:
                center = (
                    mean([m["lat"] for m in markers_data]),
                    mean([m["lon"] for m in markers_data])
                )

        if zoom is None:
            zoom = 5

        # Create map with satellite imagery
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            zoom_control=False,
            control_scale=True,
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            width='100%',
            height='100%'
        )

        # Use provided colors or fall back to default palette
        if group_colors is None:
            group_colors = {
                1: '#FF6B6B', 2: '#4ECDC4', 3: '#45B7D1', 4: '#96CEB4',
                5: '#FFEAA7', 6: '#DDA0DD', 7: '#98D8C8', 8: '#FFD93D',
                9: '#6C5CE7', 10: '#FD79A8'
            }
        
        # Add markers with group numbers
        for mk in markers_data:
            group = mk.get('group', 1)
            color_hex = group_colors.get(group, '#888888')
            
            # Create custom HTML icon with group number
            icon_html = f"""
            <div style="
                background-color: {color_hex};
                color: white;
                border: 2px solid {'#2ECC71' if mk['name'] in self.selected_samples else 'white'};
                border-radius: 50%;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                font-size: 14px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                cursor: pointer;
                position: relative;
            " data-sample-name="{mk.get('name', '')}" 
              data-lat="{mk['lat']}" 
              data-lon="{mk['lon']}"
              class="custom-marker">
                {group}
            </div>
            """
            
            # Use DivIcon for custom HTML marker
            icon = folium.DivIcon(html=icon_html)
            
            # Create popup
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; min-width: 150px;">
                <b>{mk.get('name', 'Unknown')}</b><br>
                Location: ({mk['lat']:.4f}, {mk['lon']:.4f})<br>
                Group: {mk.get('group', 'N/A')}<br>
                <div style="color: {'green' if mk['name'] in self.selected_samples else 'gray'};">
                    {'✓ Selected' if mk['name'] in self.selected_samples else 'Click to select'}
                </div>
            </div>
            """
            
            # Add marker
            marker = folium.Marker(
                location=(mk['lat'], mk['lon']),
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{mk.get('name', 'Sample')} (Group {group})",
                icon=icon
            )
            
            marker.add_to(m)
        
        # Add selection tools and JavaScript
        self._add_selection_tools(m)
        
        # Add arrow and distance tools
        self._add_map_tools(m)
        
        # Save HTML to entro_cache directory
        html_path = self._get_map_html_path()
        m.save(html_path)
        
        # Inject QWebChannel script
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Add QWebChannel and selection handling JavaScript
        channel_script = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
        var mapBridge = null;
        new QWebChannel(qt.webChannelTransport, function(channel) {
            mapBridge = channel.objects.mapBridge;
            
            // Listen for selection changes from Python
            mapBridge.selectionChanged.connect(function(selectedSamples) {
                updateMapSelection(selectedSamples);
            });
        });
        
        function updateMapSelection(selectedSamples) {
            // Update visual state of markers based on selection
            document.querySelectorAll('.custom-marker').forEach(function(marker) {
                var sampleName = marker.dataset.sampleName;
                if (selectedSamples.includes(sampleName)) {
                    marker.style.border = '3px solid #2ECC71';
                    marker.style.boxShadow = '0 0 10px #2ECC71';
                } else {
                    marker.style.border = '2px solid white';
                    marker.style.boxShadow = '0 2px 6px rgba(0,0,0,0.3)';
                }
            });
        }

        // Cross-highlight hover events (debounced)
        var hoverTimer = null;
        var lastHoveredSample = null;

        document.addEventListener('mouseover', function(e) {
            var marker = e.target.closest('.custom-marker');
            if (marker) {
                var sampleName = marker.dataset.sampleName;
                if (sampleName === lastHoveredSample) return;
                lastHoveredSample = sampleName;
                clearTimeout(hoverTimer);
                hoverTimer = setTimeout(function() {
                    if (mapBridge) {
                        mapBridge.onMarkerHover(sampleName);
                    }
                    // Visual feedback on the marker
                    marker.style.transform = 'scale(1.4)';
                    marker.style.zIndex = '9999';
                    marker.style.transition = 'transform 0.15s ease';
                }, 50);
            }
        });

        document.addEventListener('mouseout', function(e) {
            var marker = e.target.closest('.custom-marker');
            if (marker) {
                lastHoveredSample = null;
                clearTimeout(hoverTimer);
                marker.style.transform = 'scale(1.0)';
                marker.style.zIndex = '';
                if (mapBridge) {
                    mapBridge.onMarkerUnhover();
                }
            }
        });

        // Highlight a marker externally (called from Python via runJavaScript)
        window.highlightMarker = function(sampleName) {
            document.querySelectorAll('.custom-marker').forEach(function(marker) {
                if (marker.dataset.sampleName === sampleName) {
                    marker.style.transform = 'scale(1.4)';
                    marker.style.zIndex = '9999';
                    marker.style.boxShadow = '0 0 14px #FFD700';
                    marker.style.transition = 'transform 0.15s ease, box-shadow 0.15s ease';
                }
            });
        };

        window.unhighlightAllMarkers = function() {
            document.querySelectorAll('.custom-marker').forEach(function(marker) {
                marker.style.transform = 'scale(1.0)';
                marker.style.zIndex = '';
                // Restore original box-shadow based on selection state
                var sampleName = marker.dataset.sampleName;
                if (mapBridge && mapBridge.selected_samples && mapBridge.selected_samples.includes(sampleName)) {
                    marker.style.boxShadow = '0 0 10px #2ECC71';
                } else {
                    marker.style.boxShadow = '0 2px 6px rgba(0,0,0,0.3)';
                }
            });
        };
        </script>
        """
        
        # Insert before closing body tag
        html_content = html_content.replace('</body>', channel_script + '</body>')
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.web_view.setUrl(QUrl.fromLocalFile(html_path))
        
    def _add_selection_tools(self, folium_map):
        """Add interactive selection functionality to the map."""
        selection_js = """
        <script>
        (function() {
            var selectedMarkers = [];
            var isBoxSelecting = false;
            var boxSelectStart = null;
            var selectionBox = null;
            var ctrlPressed = false;
            var shiftPressed = false;
            
            // Global flags to check if tools are active
            window.isMeasurementModeActive = false;
            window.isArrowModeActive = false;
            window.isCircleSelectionActive = false;
            
            // Track modifier keys
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Control') ctrlPressed = true;
                if (e.key === 'Shift') shiftPressed = true;
            });
            
            document.addEventListener('keyup', function(e) {
                if (e.key === 'Control') ctrlPressed = false;
                if (e.key === 'Shift') shiftPressed = false;
            });
            
            // Wait for map to be available
            function initSelectionTool() {
                var mapKeys = Object.keys(window).filter(key => key.startsWith('map_'));
                if (mapKeys.length === 0) {
                    setTimeout(initSelectionTool, 500);
                    return;
                }
                
                var mapInstance = window[mapKeys[0]];
                
                // Handle marker clicks
                document.addEventListener('click', function(e) {
                    // Don't handle marker clicks if any tool mode is active
                    if (window.isMeasurementModeActive || window.isArrowModeActive || window.isCircleSelectionActive) {
                        console.log('Tool active, skipping marker click');
                        return;
                    }
                    
                    if (e.target.classList.contains('custom-marker')) {
                        e.stopPropagation();
                        e.preventDefault();
                        var sampleName = e.target.dataset.sampleName;
                        
                        console.log('Marker clicked:', sampleName);
                        
                        if (ctrlPressed || shiftPressed) {
                            // Multi-selection
                            var index = selectedMarkers.indexOf(sampleName);
                            if (index > -1) {
                                selectedMarkers.splice(index, 1);
                            } else {
                                selectedMarkers.push(sampleName);
                            }
                            
                            if (mapBridge) {
                                mapBridge.onMultiSelection(JSON.stringify(selectedMarkers));
                            }
                        } else {
                            // Single selection toggle
                            if (mapBridge) {
                                mapBridge.onMarkerClick(sampleName);
                            }
                        }
                    }
                });
                
                // Box selection with mouse drag
                var startLat, startLng;
                
                mapInstance.on('mousedown', function(e) {
                    if (e.originalEvent.shiftKey) {
                        isBoxSelecting = true;
                        boxSelectStart = e.latlng;
                        startLat = e.latlng.lat;
                        startLng = e.latlng.lng;
                        
                        // Create selection box
                        if (!selectionBox) {
                            selectionBox = L.rectangle([[startLat, startLng], [startLat, startLng]], {
                                color: '#2ECC71',
                                weight: 2,
                                opacity: 0.8,
                                fillOpacity: 0.2,
                                fillColor: '#2ECC71'
                            }).addTo(mapInstance);
                        }
                        
                        mapInstance.dragging.disable();
                        e.originalEvent.preventDefault();
                    }
                });
                
                mapInstance.on('mousemove', function(e) {
                    if (isBoxSelecting && selectionBox) {
                        var bounds = L.latLngBounds(boxSelectStart, e.latlng);
                        selectionBox.setBounds(bounds);
                    }
                });
                
                mapInstance.on('mouseup', function(e) {
                    if (isBoxSelecting) {
                        isBoxSelecting = false;
                        mapInstance.dragging.enable();
                        
                        if (selectionBox) {
                            var bounds = selectionBox.getBounds();
                            
                            // Find all markers within bounds
                            var markersInBounds = [];
                            document.querySelectorAll('.custom-marker').forEach(function(marker) {
                                var lat = parseFloat(marker.dataset.lat);
                                var lon = parseFloat(marker.dataset.lon);
                                var name = marker.dataset.sampleName;
                                
                                if (bounds.contains(L.latLng(lat, lon))) {
                                    markersInBounds.push(name);
                                }
                            });
                            
                            // Send to Python
                            if (mapBridge && markersInBounds.length > 0) {
                                mapBridge.onBoxSelection(JSON.stringify(markersInBounds));
                            }
                            
                            // Remove selection box
                            mapInstance.removeLayer(selectionBox);
                            selectionBox = null;
                        }
                    }
                });
                
                console.log('Selection tool initialized');
            }
            
            // Initialize after DOM is ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    setTimeout(initSelectionTool, 1000);
                });
            } else {
                setTimeout(initSelectionTool, 1000);
            }
        })();
        </script>
        """
        
        folium_map.get_root().html.add_child(folium.Element(selection_js))
        
    def _add_map_tools(self, folium_map):
        """Add arrow drawing, distance measurement, and circle selection tools."""
        try:
            from .arrow_tool import SimpleArrowTool
            from .distance_tool import DistanceTool
            from .circle_selection_tool import CircleSelectionTool
            
            map_var_name = folium_map.get_name()
            
            # Add arrow tool at top-left
            arrow_html = SimpleArrowTool.get_arrow_html(map_var_name, position="topleft")
            folium_map.get_root().html.add_child(folium.Element(arrow_html))
            
            # Add distance tool below arrow tool (positioned right below the clear button)
            distance_html = DistanceTool.get_distance_html(map_var_name, position="topleft", top_offset=144)
            folium_map.get_root().html.add_child(folium.Element(distance_html))
            
            # Add circle selection tool below distance tool
            circle_html = CircleSelectionTool.get_circle_selection_html(map_var_name, position="topleft", top_offset=198)
            folium_map.get_root().html.add_child(folium.Element(circle_html))
            
        except Exception as e:
            print(f"Warning: Could not add map tools: {e}")
            
    def update_selected_markers(self, selected_names):
        """
        Update the visual state of markers based on selection.
        
        Args:
            selected_names: List of selected sample names
        """
        self.selected_samples = selected_names
        self.bridge.updateSelection(selected_names)
        # Re-render to update marker colors
        self.render_map(self.markers_data, group_colors=self.group_colors)
        
    def set_selection(self, sample_names):
        """Set selection to specific samples."""
        self.selected_samples = sample_names
        self.bridge.updateSelection(sample_names)
        self.selectionChanged.emit(self.selected_samples)
        
    def clear_selection(self):
        """Clear all selected samples."""
        self.selected_samples = []
        self.bridge.updateSelection([])
        self.selectionChanged.emit(self.selected_samples)
        self.render_map(self.markers_data, group_colors=self.group_colors)
        
    def get_selected_samples(self):
        """Return list of selected sample names."""
        return self.selected_samples
    
    def zoom_to_location(self, lat, lon, sample_name=None):
        """
        Zoom the map to a specific location and optionally highlight a sample.
        
        Args:
            lat: Latitude
            lon: Longitude
            sample_name: Optional sample name to highlight
        """
        # Re-render map centered on the location with higher zoom
        self.render_map(self.markers_data, center=(lat, lon), zoom=12, group_colors=self.group_colors)
        
        # If sample name provided, highlight it temporarily
        if sample_name:
            # Execute JavaScript to highlight the marker
            js_code = f"""
            setTimeout(function() {{
                var markers = document.querySelectorAll('.custom-marker');
                markers.forEach(function(marker) {{
                    if (marker.dataset.sampleName === '{sample_name}') {{
                        // Add pulse animation
                        marker.style.animation = 'pulse 2s 3';
                        setTimeout(function() {{
                            marker.style.animation = '';
                        }}, 6000);
                    }}
                }});
            }}, 500);
            """
            self.web_view.page().runJavaScript(js_code)

    def highlight_marker(self, sample_name):
        """Highlight a specific marker on the map (called from PSD hover)."""
        js = f"if (window.highlightMarker) window.highlightMarker('{sample_name}');"
        self.web_view.page().runJavaScript(js)

    def unhighlight_all_markers(self):
        """Reset all marker highlights."""
        js = "if (window.unhighlightAllMarkers) window.unhighlightAllMarkers();"
        self.web_view.page().runJavaScript(js)
