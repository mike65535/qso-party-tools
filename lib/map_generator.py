#!/usr/bin/env python3
import json
from lib.vendor_assets import leaflet_turf_head_html

class NYMapGenerator:
    def __init__(self, boundaries_file, county_names_file):
        """Initialize with NY county boundaries GeoJSON file and county names mapping"""
        with open(boundaries_file, 'r') as f:
            self.boundaries = json.load(f)
        with open(county_names_file, 'r') as f:
            self.county_names = json.load(f)

    def _get_base_map_js(self):
        """Generate the base map JavaScript code"""
        return f'''
        const boundaries = {json.dumps(self.boundaries)};

        const map = L.map('map', {{ zoomDelta: 0.25, zoomSnap: 0.25 }});

        // Create NY state boundary merge (union all counties into one shape)
        const allFeatures = boundaries.features;
        let merged = allFeatures[0];
        for (let i = 1; i < allFeatures.length; i++) {{
            try {{
                merged = turf.union(merged, allFeatures[i]);
            }} catch(e) {{
                console.log('Union failed for feature', i);
            }}
        }}

        // Add county layers with thin borders
        L.geoJSON(boundaries, {{
            style: {{
                fillColor: '#e8e8e8',
                weight: 0.5,
                opacity: 0.8,
                color: '#666',
                fillOpacity: 0.7
            }},
            interactive: false
        }}).addTo(map);

        // Add mask layer (white background outside NY)
        if (merged) {{
            const worldPolygon = turf.bboxPolygon([-180, -90, 180, 90]);

            try {{
                const mask = turf.difference(worldPolygon, merged);
                if (mask) {{
                    L.geoJSON(mask, {{
                        style: {{
                            fillColor: 'white',
                            fillOpacity: 1,
                            weight: 0,
                            stroke: false
                        }},
                        interactive: false,
                        pane: 'overlayPane'
                    }}).addTo(map);
                }}
            }} catch(e) {{
                console.log('Mask creation failed:', e);
            }}

            // Add NY state boundary outline (using merged shape, not individual counties)
            L.geoJSON(merged, {{
                style: {{
                    fillColor: 'transparent',
                    weight: 3,
                    opacity: 1,
                    color: '#1a252f',
                    fillOpacity: 0
                }},
                interactive: false
            }}).addTo(map);
        }}

        // Fit map to NY bounds
        const bounds = L.geoJSON(boundaries).getBounds();
        map.fitBounds(bounds, {{padding: [20, 20]}});
        '''

    def generate_static_map_html(self, output_file, title="NY Map"):
        """Generate a static NY map with proper borders and styling"""

        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    {leaflet_turf_head_html()}
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ height: 100vh; width: 100%; background: white; }}
    </style>
</head>
<body>
    <div id="map"></div>

    <script>
        {self._get_base_map_js()}
    </script>
</body>
</html>'''

        with open(output_file, 'w') as f:
            f.write(html_content)

        print(f"Static NY map generated: {output_file}")
