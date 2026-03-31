"""
Distance measurement tool for interactive maps.
"""


class DistanceTool:
    @staticmethod
    def get_distance_html(map_var_name="map", position="topleft", top_offset=90):
        """
        Returns the HTML and JavaScript code for distance measurement functionality.
        Styled to match Leaflet.draw toolbar appearance.
        
        Args:
            map_var_name: The JavaScript variable name for the Leaflet map instance
            position: Position of the toolbar ('topleft', 'topright', 'bottomleft', 'bottomright')
            top_offset: Vertical offset from top (or bottom for bottom positions)
            
        Returns:
            str: Complete HTML and JavaScript code for distance measurement functionality
        """
        position_styles = {
            "topleft": f"top: {top_offset}px; left: 10px;",
            "topright": f"top: {top_offset}px; right: 10px;",
            "bottomleft": f"bottom: {top_offset}px; left: 10px;",
            "bottomright": f"bottom: {top_offset}px; right: 10px;"
        }
        
        pos_style = position_styles.get(position, position_styles["topleft"])
        
        return f"""
        <style>
        .distance-measure-toolbar {{
            position: absolute;
            {pos_style}
            z-index: 1000;
            pointer-events: auto;
        }}
        .distance-measure-toolbar .leaflet-draw-section {{
            position: relative;
            display: block;
        }}
        .distance-measure-toolbar a {{
            background-color: #fff;
            border: 1px solid #ccc;
            width: 26px;
            height: 26px;
            line-height: 24px;
            display: block;
            text-align: center;
            text-decoration: none;
            color: black;
            cursor: pointer;
            box-shadow: 0 1px 5px rgba(0,0,0,0.2);
        }}
        .distance-measure-toolbar a:hover {{
            background-color: #f4f4f4;
        }}
        .distance-measure-toolbar .distance-measure-active {{
            background-color: #a0c5e8;
            border-color: #58a1db;
        }}
        .distance-measure-toolbar .distance-measure-active:hover {{
            background-color: #8fb8dc;
        }}
        .distance-measure-toolbar .leaflet-draw-draw-ruler {{
            background-image: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 21H3L3 3h18v18z"></path><line x1="7" y1="3" x2="7" y2="8"></line><line x1="11" y1="3" x2="11" y2="6"></line><line x1="15" y1="3" x2="15" y2="8"></line><line x1="19" y1="3" x2="19" y2="6"></line></svg>');
            background-position: 4px 4px;
            background-repeat: no-repeat;
            background-size: 18px 18px;
        }}
        .distance-measure-toolbar .leaflet-draw-draw-clear-measure {{
            background-image: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>');
            background-position: 4px 4px;
            background-repeat: no-repeat;
            background-size: 18px 18px;
        }}
        .distance-popup {{
            font-family: Arial, sans-serif;
            font-size: 14px;
            font-weight: bold;
            padding: 4px 8px;
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #3388ff;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            color: #3388ff;
        }}
        .distance-line {{
            stroke: #3388ff;
            stroke-width: 3;
            stroke-dasharray: 10, 5;
            stroke-opacity: 0.8;
        }}
        </style>
        
        <div class="distance-measure-toolbar leaflet-bar leaflet-control">
            <div class="leaflet-draw-section">
                <a id="distance-measure-btn" 
                   class="leaflet-draw-draw-ruler" 
                   href="#" 
                   title="Measure distance between two sample points">
                </a>
                <a id="distance-clear-btn" 
                   class="leaflet-draw-draw-clear-measure" 
                   href="#" 
                   title="Clear distance measurements">
                </a>
            </div>
        </div>

        <script>
        (function() {{
            // Wait for map to be available
            function initDistanceTool() {{
                var mapInstance = window.{map_var_name};
                
                if (!mapInstance) {{
                    // Try to find map instance dynamically
                    var mapKeys = Object.keys(window).filter(key => key.startsWith('map_'));
                    if (mapKeys.length > 0) {{
                        mapInstance = window[mapKeys[0]];
                    }}
                }}
                
                if (!mapInstance) {{
                    console.warn('Map instance not found for distance tool, retrying...');
                    setTimeout(initDistanceTool, 500);
                    return;
                }}
                
                console.log('Distance tool initialized with map:', mapInstance);
                
                var isMeasuring = false;
                var measurementLayer = L.layerGroup().addTo(mapInstance);
                var firstMarker = null;
                var firstMarkerData = null;
                var previewLine = null;
                var measureButton = document.getElementById('distance-measure-btn');
                var clearButton = document.getElementById('distance-clear-btn');
                var currentMeasurements = [];
                var highlightedMarkers = [];
                
                if (!measureButton || !clearButton) {{
                    console.error('Distance tool buttons not found');
                    return;
                }}
                
                // Function to highlight/unhighlight markers for measurement
                function highlightMarkersForMeasurement(highlight) {{
                    var markers = document.querySelectorAll('.custom-marker');
                    markers.forEach(function(marker) {{
                        if (highlight) {{
                            marker.style.cursor = 'pointer';
                            marker.style.transition = 'all 0.2s';
                            // Add subtle pulse animation
                            if (!marker.style.animation) {{
                                marker.style.animation = 'pulse 1.5s infinite';
                            }}
                        }} else {{
                            // Only remove measurement-related styles, not selection styles
                            marker.style.cursor = '';
                            marker.style.animation = '';
                            marker.style.transition = '';
                            // Only remove bright green measurement highlight (#00ff00)
                            // Keep dark green selection highlight (#2ECC71) intact
                            if (marker.style.border && marker.style.border.includes('#00ff00')) {{
                                // Restore to original or remove only measurement style
                                marker.style.border = marker.originalBorder || '';
                                marker.style.boxShadow = marker.originalBoxShadow || '';
                            }}
                        }}
                    }});
                    
                    // Add CSS animation if not exists
                    if (highlight && !document.getElementById('pulse-animation')) {{
                        var style = document.createElement('style');
                        style.id = 'pulse-animation';
                        style.innerHTML = `
                            @keyframes pulse {{
                                0% {{ transform: scale(1); }}
                                50% {{ transform: scale(1.1); }}
                                100% {{ transform: scale(1); }}
                            }}
                        `;
                        document.head.appendChild(style);
                    }}
                }}
                
                // Measure button click handler
                measureButton.addEventListener('click', function(e) {{
                    e.preventDefault();
                    isMeasuring = !isMeasuring;
                    
                    // Set global flag to prevent marker selection
                    window.isMeasurementModeActive = isMeasuring;
                    
                    if (isMeasuring) {{
                        this.className = this.className + ' distance-measure-active';
                        mapInstance.getContainer().style.cursor = 'crosshair';
                        // Highlight all markers to show they're clickable
                        highlightMarkersForMeasurement(true);
                        console.log('Distance measurement mode activated - click on two sample points');
                    }} else {{
                        this.className = this.className.replace(' distance-measure-active', '');
                        mapInstance.getContainer().style.cursor = '';
                        firstMarker = null;
                        firstMarkerData = null;
                        if (previewLine) {{
                            mapInstance.removeLayer(previewLine);
                            previewLine = null;
                        }}
                        // Remove highlight from markers
                        highlightMarkersForMeasurement(false);
                        console.log('Distance measurement mode deactivated');
                    }}
                }});
                
                // Clear button click handler - only clears distance measurements
                clearButton.addEventListener('click', function(e) {{
                    e.preventDefault();
                    
                    // Clear all distance measurement lines
                    measurementLayer.clearLayers();
                    currentMeasurements = [];
                    
                    // Only deactivate if tool was active
                    if (isMeasuring) {{
                        isMeasuring = false;
                        window.isMeasurementModeActive = false;
                        measureButton.className = measureButton.className.replace(' distance-measure-active', '');
                        mapInstance.getContainer().style.cursor = '';
                        highlightMarkersForMeasurement(false);
                    }}
                    
                    // Reset first marker if in the middle of measurement
                    if (firstMarker) {{
                        // Only reset the green measurement highlight
                        if (firstMarker.style.border && firstMarker.style.border.includes('#00ff00')) {{
                            firstMarker.style.boxShadow = firstMarker.originalBoxShadow || '';
                            firstMarker.style.border = firstMarker.originalBorder || '';
                        }}
                        firstMarker = null;
                    }}
                    firstMarkerData = null;
                    
                    if (previewLine) {{
                        mapInstance.removeLayer(previewLine);
                        previewLine = null;
                    }}
                    
                    console.log('Distance measurements cleared');
                }});
                
                // Handle marker clicks for distance measurement
                document.addEventListener('click', function(e) {{
                    if (!isMeasuring) return;
                    
                    // Check if click is on a marker
                    if (e.target.classList && e.target.classList.contains('custom-marker')) {{
                        e.stopPropagation();
                        e.preventDefault();
                        
                        var markerElement = e.target;
                        var lat = parseFloat(markerElement.dataset.lat);
                        var lon = parseFloat(markerElement.dataset.lon);
                        var sampleName = markerElement.dataset.sampleName;
                        
                        if (!firstMarker) {{
                            // First marker clicked
                            firstMarker = markerElement;
                            firstMarkerData = {{
                                lat: lat,
                                lon: lon,
                                name: sampleName
                            }};
                            // Store original styles before applying measurement highlight
                            markerElement.originalBorder = markerElement.style.border || '';
                            markerElement.originalBoxShadow = markerElement.style.boxShadow || '';
                            // Apply bright green measurement highlight
                            markerElement.style.boxShadow = '0 0 15px #00ff00';
                            markerElement.style.border = '3px solid #00ff00';
                            console.log('First point selected:', sampleName, 'at', lat, lon);
                        }} else if (markerElement !== firstMarker) {{
                            // Second marker clicked (must be different from first)
                            var secondMarkerData = {{
                                lat: lat,
                                lon: lon,
                                name: sampleName
                            }};
                            
                            // Create measurement between the two points
                            var startLatLng = L.latLng(firstMarkerData.lat, firstMarkerData.lon);
                            var endLatLng = L.latLng(secondMarkerData.lat, secondMarkerData.lon);
                            createDistanceMeasurement(startLatLng, endLatLng, firstMarkerData.name, secondMarkerData.name);
                            
                            // Reset first marker to its original styling (which may include selection)
                            firstMarker.style.boxShadow = firstMarker.originalBoxShadow || '';
                            firstMarker.style.border = firstMarker.originalBorder || '';
                            
                            // Clear selection
                            firstMarker = null;
                            firstMarkerData = null;
                            
                            if (previewLine) {{
                                mapInstance.removeLayer(previewLine);
                                previewLine = null;
                            }}
                            
                            console.log('Distance measured between', firstMarkerData.name, 'and', sampleName);
                        }}
                    }}
                }});
                
                // Mouse move handler for preview line when first marker is selected
                document.addEventListener('mousemove', function(e) {{
                    if (!isMeasuring || !firstMarker) return;
                    
                    // Check if hovering over a marker
                    var hoverElement = document.elementFromPoint(e.clientX, e.clientY);
                    if (hoverElement && hoverElement.classList && hoverElement.classList.contains('custom-marker') && hoverElement !== firstMarker) {{
                        var lat = parseFloat(hoverElement.dataset.lat);
                        var lon = parseFloat(hoverElement.dataset.lon);
                        
                        if (previewLine) {{
                            mapInstance.removeLayer(previewLine);
                        }}
                        
                        var startLatLng = L.latLng(firstMarkerData.lat, firstMarkerData.lon);
                        var endLatLng = L.latLng(lat, lon);
                        
                        // Calculate distance for preview
                        var distance = startLatLng.distanceTo(endLatLng);
                        var distanceText = distance < 1000 ? 
                            Math.round(distance) + ' m' : 
                            (distance / 1000).toFixed(2) + ' km';
                        
                        previewLine = L.polyline([startLatLng, endLatLng], {{
                            color: '#3388ff',
                            weight: 2,
                            opacity: 0.5,
                            dashArray: '5, 5'
                        }});
                        
                        previewLine.bindTooltip(distanceText, {{
                            permanent: true,
                            direction: 'center',
                            className: 'distance-popup'
                        }});
                        
                        mapInstance.addLayer(previewLine);
                    }} else if (previewLine) {{
                        // Remove preview if not hovering over a valid marker
                        mapInstance.removeLayer(previewLine);
                        previewLine = null;
                    }}
                }});
                
                // Create distance measurement between two sample points
                function createDistanceMeasurement(start, end, startName, endName) {{
                    var measurementGroup = L.layerGroup();
                    
                    // Calculate distance using Haversine formula
                    var distance = start.distanceTo(end);
                    var distanceText;
                    
                    if (distance < 1000) {{
                        distanceText = Math.round(distance) + ' m';
                    }} else {{
                        distanceText = (distance / 1000).toFixed(2) + ' km';
                    }}
                    
                    // Create the measurement line with thicker weight
                    var measureLine = L.polyline([start, end], {{
                        color: '#ff4444',
                        weight: 4,
                        opacity: 0.9
                    }});
                    
                    // Add distance label as permanent tooltip on the line
                    measureLine.bindTooltip(distanceText, {{
                        permanent: true,
                        direction: 'center',
                        className: 'distance-popup'
                    }});
                    
                    // Add popup with detailed information when clicking the line
                    var popupContent = `
                        <div style="font-family: Arial, sans-serif; min-width: 250px;">
                            <h4 style="margin: 0 0 8px 0; color: #ff4444;">Distance Measurement</h4>
                            <b>From:</b> ${{startName}}<br>
                            <b>To:</b> ${{endName}}<br>
                            <hr style="margin: 8px 0;">
                            <b>Point 1:</b> (${{start.lat.toFixed(6)}}, ${{start.lng.toFixed(6)}})<br>
                            <b>Point 2:</b> (${{end.lat.toFixed(6)}}, ${{end.lng.toFixed(6)}})<br>
                            <b>Distance:</b> <span style="color: #ff4444; font-size: 16px;">$${{distanceText}}</span><br>
                            <b>Bearing:</b> ${{calculateBearing(start, end).toFixed(1)}}°
                        </div>
                    `;
                    
                    measureLine.bindPopup(popupContent);
                    
                    // Add only the line to the group
                    measurementGroup.addLayer(measureLine);
                    
                    // Add to main layer
                    measurementLayer.addLayer(measurementGroup);
                    
                    // Store measurement
                    currentMeasurements.push({{
                        start: start,
                        end: end,
                        startName: startName,
                        endName: endName,
                        distance: distance,
                        group: measurementGroup
                    }});
                }}
                
                // Calculate bearing between two points
                function calculateBearing(start, end) {{
                    var startLat = start.lat * Math.PI / 180;
                    var startLng = start.lng * Math.PI / 180;
                    var endLat = end.lat * Math.PI / 180;
                    var endLng = end.lng * Math.PI / 180;
                    
                    var dLng = endLng - startLng;
                    
                    var x = Math.cos(endLat) * Math.sin(dLng);
                    var y = Math.cos(startLat) * Math.sin(endLat) - 
                            Math.sin(startLat) * Math.cos(endLat) * Math.cos(dLng);
                    
                    var bearing = Math.atan2(x, y) * 180 / Math.PI;
                    return (bearing + 360) % 360;
                }}
                
                console.log('Distance tool fully initialized');
            }}
            
            // Initialize after DOM is ready
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', function() {{
                    setTimeout(initDistanceTool, 1000);
                }});
            }} else {{
                setTimeout(initDistanceTool, 1000);
            }}
        }})();
        </script>
        """


def add_distance_tool_to_map(folium_map, map_var_name=None, position="topleft", top_offset=90):
    """
    Add distance measurement tool to a Folium map.
    
    Args:
        folium_map: Folium Map object
        map_var_name: Optional map variable name (auto-detected if None)
        position: Position of the toolbar ('topleft', 'topright', 'bottomleft', 'bottomright')
        top_offset: Vertical offset from top (or bottom for bottom positions)
        
    Returns:
        Folium Map object with distance tool added
    """
    try:
        import folium
        
        # Try to get the map variable name automatically
        if map_var_name is None:
            map_var_name = folium_map.get_name()
        
        # Create distance tool HTML with specified position
        distance_html = DistanceTool.get_distance_html(map_var_name, position, top_offset)
        
        # Add to map
        folium_map.get_root().html.add_child(folium.Element(distance_html))
        
        return folium_map
        
    except ImportError:
        print("Warning: Folium not available, distance tool cannot be added")
        return folium_map
    except Exception as e:
        print(f"Warning: Could not add distance tool: {e}")
        return folium_map


# Example usage
if __name__ == "__main__":
    print("DistanceTool utility module")
    print("Use add_distance_tool_to_map() to add distance measurement functionality to your Folium maps")