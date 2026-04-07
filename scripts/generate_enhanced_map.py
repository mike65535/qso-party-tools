#!/usr/bin/env python3
"""
Generate enhanced interactive county-level QSO activity map.
Choropleth with hover tooltips and click popups showing top stations per county.

Requires a GeoJSON boundaries file for the host state (default: reference/ny_counties.json).
"""

import sqlite3
import json
import argparse
from pathlib import Path


def get_county_data(meta_db, qso_db, valid_counties):
    """Extract county QSO data from databases."""
    qso_conn = sqlite3.connect(qso_db)

    total_qsos = qso_conn.execute("SELECT COUNT(*) FROM valid_qsos").fetchone()[0]

    cursor = qso_conn.execute("""
        SELECT tx_county, tx_call, COUNT(*) as qso_count
        FROM valid_qsos
        WHERE tx_county IS NOT NULL AND tx_county != ''
        GROUP BY tx_county, tx_call
        ORDER BY tx_county, qso_count DESC
    """)

    county_qsos = {}
    county_top_stations = {}

    for county, callsign, qso_count in cursor.fetchall():
        county = county.upper()
        if valid_counties and county not in valid_counties:
            continue
        if county not in county_qsos:
            county_qsos[county] = 0
            county_top_stations[county] = []
        county_qsos[county] += qso_count
        county_top_stations[county].append({"call": callsign, "qsos": qso_count})

    for county in county_top_stations:
        county_top_stations[county].sort(key=lambda x: x["qsos"], reverse=True)
        county_top_stations[county] = county_top_stations[county][:5]

    qso_conn.close()
    return county_qsos, county_top_stations, total_qsos


def generate_map_html(meta_db, qso_db, boundaries_file, title, valid_counties, name_map):
    """Generate the complete HTML map file."""
    county_qsos, county_top_stations, total_qsos = get_county_data(meta_db, qso_db, valid_counties)

    county_data = {
        abbrev: {"qsos": qso_count, "top5": county_top_stations.get(abbrev, [])}
        for abbrev, qso_count in county_qsos.items()
    }

    total_qsos_by_county = sum(county_qsos.values())
    active_counties = len(county_qsos)
    print(f"Total QSOs in database: {total_qsos}")
    print(f"QSOs from host-state counties: {total_qsos_by_county}")
    print(f"Active counties: {active_counties}")

    try:
        with open(boundaries_file, 'r') as f:
            boundaries_json = json.dumps(json.load(f))
        print(f"Loaded boundaries from {boundaries_file}")
    except Exception as e:
        print(f"WARNING: Could not load boundaries ({e}) — map will have no county shapes")
        boundaries_json = '{"type": "FeatureCollection", "features": []}'

    num_counties = len(valid_counties) if valid_counties else '?'

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: white; }}
        #map {{ position: absolute; top: 0; bottom: 50px; left: 0; right: 0; background: white; }}
        #info {{ position: absolute; bottom: 0; left: 0; right: 0; height: 50px; background: #2c3e50; color: white; padding: 15px; text-align: center; z-index: 1000; font-size: 16px; }}
        .popup-content {{ min-width: 250px; font-size: 16px; }}
        .popup-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
        .popup-qsos {{ font-size: 16px; margin-bottom: 12px; }}
        .popup-zero {{ color: #e74c3c; font-style: italic; font-size: 16px; }}
        .callsign-item {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #ecf0f1; font-size: 15px; }}
        .callsign-rank {{ color: #95a5a6; margin-right: 8px; }}
        .callsign-call {{ font-weight: bold; color: #2980b9; }}
        .callsign-count {{ color: #7f8c8d; }}
        @media (max-width: 768px) {{
            #info {{ font-size: 14px; padding: 10px; }}
            .popup-content {{ min-width: 220px; }}
        }}
        .leaflet-interactive {{ outline: none !important; }}
        .leaflet-interactive:focus {{ outline: none !important; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="info">{title} | {total_qsos_by_county:,} QSOs from {active_counties} of {num_counties} Counties</div>
    <script>
        const boundaries = {boundaries_json};
        const countyData = {json.dumps(county_data, indent=2)};
        const nameMap = {json.dumps(name_map, indent=2)};

        const map = L.map('map', {{
            zoomControl: true, scrollWheelZoom: true, doubleClickZoom: true,
            boxZoom: true, keyboard: true, dragging: true, minZoom: 6, maxZoom: 11
        }});

        const allFeatures = boundaries.features;
        let merged = allFeatures[0];
        for (let i = 1; i < allFeatures.length; i++) {{
            try {{ merged = turf.union(merged, allFeatures[i]); }}
            catch(e) {{ console.log('Union failed for feature', i); }}
        }}

        L.tileLayer('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
            {{ attribution: '' }}).addTo(map);

        function getColor(qsos) {{
            const maxQsos = Math.max(...Object.values(countyData).map(d => d.qsos));
            if (qsos === 0) return '#e8e8e8';
            const intensity = qsos / maxQsos;
            if (intensity > 0.8) return '#800026';
            if (intensity > 0.6) return '#BD0026';
            if (intensity > 0.4) return '#E31A1C';
            if (intensity > 0.2) return '#FC4E2A';
            if (intensity > 0.1) return '#FD8D3C';
            if (intensity > 0.05) return '#FEB24C';
            return '#FED976';
        }}

        L.geoJSON(boundaries, {{
            style: function(feature) {{
                const abbrev = nameMap[feature.properties.NAME];
                const qsos = countyData[abbrev] ? countyData[abbrev].qsos : 0;
                return {{ fillColor: getColor(qsos), weight: 1, opacity: 0.8, color: '#666', fillOpacity: 0.7 }};
            }},
            onEachFeature: function(feature, layer) {{
                const countyName = feature.properties.NAME;
                const abbrev = nameMap[countyName];
                const data = countyData[abbrev];

                let popup = `<div class="popup-content"><div class="popup-title">${{abbrev}} - ${{countyName}}</div>`;
                if (data && data.qsos > 0) {{
                    popup += `<div class="popup-qsos">Total QSOs: ${{data.qsos.toLocaleString()}}</div>`;
                    if (data.top5.length > 0) {{
                        popup += '<div><strong>Top Stations:</strong></div>';
                        data.top5.forEach((s, i) => {{
                            popup += `<div class="callsign-item">
                                <span><span class="callsign-rank">${{i+1}}.</span><span class="callsign-call">${{s.call}}</span></span>
                                <span class="callsign-count">${{s.qsos.toLocaleString()}}</span>
                            </div>`;
                        }});
                    }}
                }} else {{
                    popup += '<div class="popup-zero">No QSO activity recorded</div>';
                }}
                popup += '</div>';
                layer.bindPopup(popup);

                layer.on({{
                    mouseover: function(e) {{
                        e.target.setStyle({{ weight: 3, color: '#2c3e50', fillOpacity: 0.9 }});
                        const qsoCount = data && data.qsos > 0 ? data.qsos.toLocaleString() : '0';
                        e.target.bindTooltip(`${{abbrev}} - ${{countyName}}<br>${{qsoCount}} QSOs`,
                            {{ permanent: false, direction: 'top' }}).openTooltip();
                    }},
                    mouseout: function(e) {{
                        e.target.setStyle({{ weight: 1, color: '#666', fillOpacity: 0.7 }});
                        e.target.closeTooltip();
                        e.target.closePopup();
                    }}
                }});
            }}
        }}).addTo(map);

        if (merged) {{
            try {{
                const mask = turf.difference(turf.bboxPolygon([-180, -90, 180, 90]), merged);
                if (mask) {{
                    L.geoJSON(mask, {{
                        style: {{ fillColor: 'white', fillOpacity: 1, weight: 0, stroke: false }},
                        interactive: false, pane: 'overlayPane'
                    }}).addTo(map);
                }}
            }} catch(e) {{ console.log('Mask failed:', e); }}

            L.geoJSON(merged, {{
                style: {{ fillColor: 'transparent', weight: 3, opacity: 1, color: '#1a252f', fillOpacity: 0 }},
                interactive: false
            }}).addTo(map);
        }}

        map.fitBounds(L.geoJSON(boundaries).getBounds(), {{padding: [30, 30]}});
    </script>
</body>
</html>'''


def main():
    # Default NY county name-to-abbreviation mapping
    DEFAULT_NAME_MAP = {
        "Albany": "ALB", "Allegany": "ALL", "Broome": "BRM", "Bronx": "BRX",
        "Cattaraugus": "CAT", "Cayuga": "CAY", "Chautauqua": "CHA", "Chemung": "CHE",
        "Chenango": "CGO", "Clinton": "CLI", "Columbia": "COL", "Cortland": "COR",
        "Delaware": "DEL", "Dutchess": "DUT", "Erie": "ERI", "Essex": "ESS",
        "Franklin": "FRA", "Fulton": "FUL", "Genesee": "GEN", "Greene": "GRE",
        "Hamilton": "HAM", "Herkimer": "HER", "Jefferson": "JEF", "Kings": "KIN",
        "Lewis": "LEW", "Livingston": "LIV", "Madison": "MAD", "Monroe": "MON",
        "Montgomery": "MTG", "Nassau": "NAS", "New York": "NEW", "Niagara": "NIA",
        "Oneida": "ONE", "Onondaga": "ONO", "Ontario": "ONT", "Orange": "ORA",
        "Orleans": "ORL", "Oswego": "OSW", "Otsego": "OTS", "Putnam": "PUT",
        "Queens": "QUE", "Rensselaer": "REN", "Richmond": "RIC", "Rockland": "ROC",
        "Saratoga": "SAR", "Schenectady": "SCH", "Schoharie": "SCO", "Schuyler": "SCU",
        "Seneca": "SEN", "Steuben": "STE", "St. Lawrence": "STL", "Suffolk": "SUF",
        "Sullivan": "SUL", "Tioga": "TIO", "Tompkins": "TOM", "Ulster": "ULS",
        "Warren": "WAR", "Washington": "WAS", "Wayne": "WAY", "Westchester": "WES",
        "Wyoming": "WYO", "Yates": "YAT"
    }

    parser = argparse.ArgumentParser(description='Generate enhanced county activity map')
    parser.add_argument('--meta-db', required=True, help='Path to contest_meta.db')
    parser.add_argument('--qso-db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--boundaries', default='reference/ny_counties.json',
                        help='GeoJSON county boundaries file (default: reference/ny_counties.json)')
    parser.add_argument('--name-map', help='JSON file mapping county names to abbreviations (uses NY defaults if omitted)')
    parser.add_argument('--title', default='QSOs made from host-state stations')
    args = parser.parse_args()

    name_map = DEFAULT_NAME_MAP
    if args.name_map:
        with open(args.name_map, 'r') as f:
            name_map = json.load(f)

    valid_counties = set(name_map.values())

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    html = generate_map_html(args.meta_db, args.qso_db, args.boundaries,
                             args.title, valid_counties, name_map)

    with open(args.output, 'w') as f:
        f.write(html)
    print(f"Enhanced map saved to {args.output}")


if __name__ == "__main__":
    main()
