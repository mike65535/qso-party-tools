#!/usr/bin/env python3
"""
County-level QSO activity animation.
Shows all station activity by NY county over the contest period.
"""

import json
import sqlite3
import argparse
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.animation_controls import get_controls_html, get_controls_css, get_controls_js
from lib.animation_legend import get_legend_html, get_legend_css, get_legend_js

ANIMATION_SPEEDS = [1, 5, 10, 50]
COLOR_THRESHOLDS = [0, 0.05, 0.15, 0.35, 0.65]
COLOR_PALETTE = ['#f0f0f0', '#d4c5a9', '#f4e4a6', '#f7b32b', '#d73027', '#a50f15']

NY_COUNTY_NAMES = {
    "ALB": "Albany County", "ALL": "Allegany County", "BRX": "Bronx County", "BRM": "Broome County",
    "CAT": "Cattaraugus County", "CAY": "Cayuga County", "CHA": "Chautauqua County", "CHE": "Chemung County",
    "CGO": "Chenango County", "CLI": "Clinton County", "COL": "Columbia County", "COR": "Cortland County",
    "DEL": "Delaware County", "DUT": "Dutchess County", "ERI": "Erie County", "ESS": "Essex County",
    "FRA": "Franklin County", "FUL": "Fulton County", "GEN": "Genesee County", "GRE": "Greene County",
    "HAM": "Hamilton County", "HER": "Herkimer County", "JEF": "Jefferson County", "KIN": "Kings County",
    "LEW": "Lewis County", "LIV": "Livingston County", "MAD": "Madison County", "MON": "Monroe County",
    "MTG": "Montgomery County", "NAS": "Nassau County", "NEW": "New York County", "NIA": "Niagara County",
    "ONE": "Oneida County", "ONO": "Onondaga County", "ONT": "Ontario County", "ORA": "Orange County",
    "ORL": "Orleans County", "OSW": "Oswego County", "OTS": "Otsego County", "PUT": "Putnam County",
    "QUE": "Queens County", "REN": "Rensselaer County", "RIC": "Richmond County", "ROC": "Rockland County",
    "SAR": "Saratoga County", "SCH": "Schenectady County", "SCO": "Schoharie County", "SCU": "Schuyler County",
    "SEN": "Seneca County", "STL": "St. Lawrence County", "STE": "Steuben County", "SUF": "Suffolk County",
    "SUL": "Sullivan County", "TIO": "Tioga County", "TOM": "Tompkins County", "ULS": "Ulster County",
    "WAR": "Warren County", "WAS": "Washington County", "WAY": "Wayne County", "WES": "Westchester County",
    "WYO": "Wyoming County", "YAT": "Yates County",
}


def _detect_contest_window(qso_db, contest_start, contest_end):
    """Derive actual contest date from DB (handles year mismatches between config and data)."""
    from datetime import timedelta as _td
    conn = sqlite3.connect(qso_db)
    row = conn.execute("""
        SELECT DATE(datetime) FROM qsos WHERE tx_county IS NOT NULL AND tx_county != ''
        GROUP BY DATE(datetime) ORDER BY COUNT(*) DESC LIMIT 1
    """).fetchone()
    conn.close()
    if not row:
        return contest_start, contest_end
    contest_date = row[0]
    start_time_str = contest_start.split('T')[-1] if 'T' in contest_start else contest_start[11:]
    end_time_str   = contest_end.split('T')[-1]   if 'T' in contest_end   else contest_end[11:]
    s = datetime.strptime(f"{contest_date} {start_time_str}", '%Y-%m-%d %H:%M:%S')
    e_base = datetime.strptime(f"2000-01-01 {end_time_str}", '%Y-%m-%d %H:%M:%S')
    s_base = datetime.strptime(f"2000-01-01 {start_time_str}", '%Y-%m-%d %H:%M:%S')
    offset = 1 if e_base <= s_base else 0
    e_date = (s + _td(days=offset)).strftime('%Y-%m-%d')
    e = datetime.strptime(f"{e_date} {end_time_str}", '%Y-%m-%d %H:%M:%S')
    actual_start = s.strftime('%Y-%m-%dT%H:%M:%S')
    actual_end   = e.strftime('%Y-%m-%dT%H:%M:%S')
    print(f"Contest date detected from DB: {contest_date} → window {actual_start} to {actual_end}")
    return actual_start, actual_end


def generate_county_animation(qso_db, boundaries_file, output_file, contest_start, contest_end, title):
    with open(boundaries_file, 'r') as f:
        boundaries_data = json.load(f)

    contest_start, contest_end = _detect_contest_window(qso_db, contest_start, contest_end)

    conn = sqlite3.connect(qso_db)
    cursor = conn.execute("""
        SELECT datetime, station_call, tx_county
        FROM qsos
        WHERE tx_county IS NOT NULL AND tx_county != ''
        ORDER BY datetime
    """)
    all_qsos = [{'t': r[0].replace(' ', 'T'), 's': r[1], 'c': r[2]} for r in cursor.fetchall()]
    conn.close()

    print(f"Loaded {len(all_qsos)} QSOs")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ height: 95vh; width: 100%; background-color: white; }}
        .leaflet-top {{ top: 40px; }}
        {get_controls_css()}
        {get_legend_css()}
    </style>
</head>
<body>
    <div id="map"></div>
    {get_controls_html()}
    {get_legend_html()}
    <script>
        const countyNames = {json.dumps(NY_COUNTY_NAMES, indent=8)};
        const boundariesData = {json.dumps(boundaries_data)};
        const allQSOs = {json.dumps(all_qsos, indent=8)};

        let map, isPlaying = false, animationInterval, speed = 1;
        let currentTime = new Date('{contest_start}Z');
        const startTime = new Date('{contest_start}Z');
        const endTime = new Date('{contest_end}Z');
        const countyCoords = {{}};
        let countyLayer;

        {get_legend_js(str(COLOR_THRESHOLDS), str(COLOR_PALETTE), "QSOs per County")}

        function playPause() {{
            if (isPlaying) {{
                clearInterval(animationInterval);
                document.getElementById('playBtn').textContent = '▶ Play';
                isPlaying = false;
            }} else {{
                animationInterval = setInterval(() => {{
                    currentTime = new Date(currentTime.getTime() + 60000);
                    if (currentTime > endTime) {{ currentTime = endTime; playPause(); }}
                    updateDisplay();
                }}, 1000 / speed);
                document.getElementById('playBtn').textContent = '⏸ Pause';
                isPlaying = true;
            }}
        }}

        function reset() {{
            if (isPlaying) playPause();
            currentTime = new Date('{contest_start}Z');
            updateDisplay();
        }}

        function changeSpeed(delta) {{
            const speeds = {ANIMATION_SPEEDS};
            let idx = speeds.indexOf(speed);
            speed = speeds[(idx + 1) % speeds.length];
            document.getElementById('speedBtn').textContent = `Speed ${{speed}}x`;
            if (isPlaying) {{ clearInterval(animationInterval); playPause(); playPause(); }}
        }}

        function seekToPosition(event) {{
            const rect = event.currentTarget.getBoundingClientRect();
            const pct = (event.clientX - rect.left) / rect.width;
            currentTime = new Date(startTime.getTime() + pct * (endTime - startTime));
            updateDisplay();
        }}

        function getCountyAbbrev(fullName) {{
            for (const [abbrev, name] of Object.entries(countyNames)) {{
                if (name === fullName + " County") return abbrev;
            }}
            return fullName.substring(0, 3).toUpperCase();
        }}

        function initMap() {{
            map = L.map('map').setView([43.0, -76.0], 7);

            const allFeatures = boundariesData.features;
            let merged = allFeatures[0];
            for (let i = 1; i < allFeatures.length; i++) {{
                try {{ merged = turf.union(merged, allFeatures[i]); }}
                catch(e) {{ console.log('Union failed', i); }}
            }}

            L.tileLayer('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
                {{ attribution: '' }}).addTo(map);

            countyLayer = L.geoJSON(boundariesData, {{
                style: () => ({{ fillColor: '#e8e8e8', weight: 0.5, opacity: 0.8, color: '#666', fillOpacity: 1.0 }}),
                onEachFeature: function(feature, layer) {{
                    const name = feature.properties.NAME;
                    const abbrev = getCountyAbbrev(name);
                    layer.bindPopup(`<b>${{abbrev}}</b><br>${{name}} County<br>QSOs: 0`);
                    layer.countyName = name;
                    layer.countyAbbrev = abbrev;
                }}
            }}).addTo(map);

            if (merged) {{
                try {{
                    const mask = turf.difference(turf.bboxPolygon([-180, -90, 180, 90]), merged);
                    if (mask) L.geoJSON(mask, {{
                        style: {{ fillColor: 'white', fillOpacity: 1, weight: 0, stroke: false }},
                        interactive: false, pane: 'overlayPane'
                    }}).addTo(map);
                }} catch(e) {{ console.log('Mask failed', e); }}

                L.geoJSON(merged, {{
                    style: {{ fillColor: 'transparent', weight: 3, opacity: 1, color: '#1a252f', fillOpacity: 0 }},
                    interactive: false
                }}).addTo(map);
            }}

            boundariesData.features.forEach(feature => {{
                const name = feature.properties.NAME;
                const bbox = turf.bbox(feature);
                countyCoords[name + " County"] = [(bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2];
            }});

            updateDisplay();
        }}

        function updateDisplay() {{
            document.getElementById('dateDisplay').textContent = currentTime.toISOString().split('T')[0];
            document.getElementById('timeDisplay').textContent = currentTime.toISOString().split('T')[1].substring(0, 5) + 'Z';

            const progress = Math.max(0, Math.min(100, (currentTime - startTime) / (endTime - startTime) * 100));
            document.getElementById('progressBar').style.width = progress + '%';

            const countyQSOs = {{}};
            const countyStations = {{}};
            let totalQSOs = 0;

            allQSOs.forEach(qso => {{
                const t = new Date(qso.t + 'Z');
                if (t >= startTime && t < currentTime) {{
                    const fullName = countyNames[qso.c];
                    if (fullName) {{
                        countyQSOs[fullName] = (countyQSOs[fullName] || 0) + 1;
                        if (!countyStations[fullName]) countyStations[fullName] = {{}};
                        countyStations[fullName][qso.s] = (countyStations[fullName][qso.s] || 0) + 1;
                        totalQSOs++;
                    }}
                }}
            }});

            const maxQSOs = Math.max(0, ...Object.values(countyQSOs));
            updateLegend(maxQSOs);

            countyLayer.eachLayer(layer => {{
                const fullName = layer.countyName + " County";
                const qsoCount = countyQSOs[fullName] || 0;
                layer.setStyle({{ fillColor: getColor(qsoCount, maxQSOs) }});

                let topText = "No activity yet";
                if (countyStations[fullName]) {{
                    topText = Object.entries(countyStations[fullName])
                        .sort((a, b) => b[1] - a[1]).slice(0, 5)
                        .map(([call, n]) => `${{call}}: ${{n}}`).join('<br>');
                }}
                layer.getPopup().setContent(
                    `<b>${{layer.countyAbbrev}}</b><br>${{layer.countyName}} County<br>QSOs: ${{qsoCount}}<br><br>Top Stations:<br>${{topText}}`
                );
            }});

            const activeCounties = Object.keys(countyQSOs).length;
            document.getElementById('statusDisplay').textContent =
                `{title} | QSOs: ${{totalQSOs}} | Active Counties: ${{activeCounties}}`;
        }}

        document.addEventListener('DOMContentLoaded', initMap);
    </script>
</body></html>'''

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(html)
    print(f"County animation saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate county-level QSO activity animation')
    parser.add_argument('--db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--boundaries', default='reference/ny_counties.json',
                        help='GeoJSON county boundaries file')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--contest-start', required=True,
                        help='Contest start datetime UTC (e.g. "2025-10-18T14:00:00")')
    parser.add_argument('--contest-end', required=True,
                        help='Contest end datetime UTC (e.g. "2025-10-19T02:00:00")')
    parser.add_argument('--title', default='County QSO Activity Animation')
    args = parser.parse_args()

    generate_county_animation(
        args.db, args.boundaries, args.output,
        args.contest_start, args.contest_end, args.title
    )


if __name__ == "__main__":
    main()
