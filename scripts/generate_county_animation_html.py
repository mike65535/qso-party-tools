#!/usr/bin/env python3
"""
County/district-level QSO activity animation.
Shows all station activity by host region over the contest period.
Works with any GeoJSON boundaries file that has COUNTY and NAME properties.
"""

import json
import sqlite3
import argparse
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.animation_controls import get_controls_html, get_controls_css, get_controls_js
from lib.vendor_assets import leaflet_turf_head_html
from lib.animation_legend import get_legend_html, get_legend_css, get_legend_js

ANIMATION_SPEEDS = [1, 2, 5, 10, 20, 50]
COLOR_THRESHOLDS = [0, 0.05, 0.15, 0.35, 0.65]
COLOR_PALETTE = ['#f0f0f0', '#d4c5a9', '#f4e4a6', '#f7b32b', '#d73027', '#a50f15']

COUNTY_ABOUT = (
    "This animation shows cumulative QSO activity by region over the contest period. "
    "Each region is colored by the number of QSOs logged by stations operating from that region. "
    "Only QSOs within the official contest window are counted; structural errors are excluded. "
    "Regions where no station submitted a log do not appear, even if they were worked by others. "
    "The color scale is relative to the current frame maximum and adjusts as the contest progresses."
)

def generate_county_animation(qso_db, boundaries_file, output_file, contest_start, contest_end, title, region_term="County", about_text=None):
    if about_text is None:
        rt = region_term.lower()
        rtp = rt + 's'
        about_text = (
            f"This animation shows cumulative QSO activity by {rt} over the contest period. "
            f"Each {rt} is colored by the number of QSOs logged by stations operating from that {rt}. "
            f"Only QSOs within the official contest window are counted; structural errors are excluded. "
            f"{rtp.capitalize()} where no station submitted a log do not appear, even if they were worked by others. "
            f"The color scale is relative to the current frame maximum and adjusts as the contest progresses."
        )

    with open(boundaries_file, 'r') as f:
        boundaries_data = json.load(f)

    # Build region name lookup from GeoJSON (COUNTY code -> NAME)
    region_names = {
        f['properties']['COUNTY']: f['properties']['NAME']
        for f in boundaries_data['features']
        if 'COUNTY' in f['properties'] and 'NAME' in f['properties']
    }

    start_db = contest_start.replace('T', ' ')
    end_db   = contest_end.replace('T', ' ')
    conn = sqlite3.connect(qso_db)
    all_qsos = [{'t': r[0].replace(' ', 'T'), 's': r[1], 'c': r[2]} for r in conn.execute(
        "SELECT datetime, station_call, tx_county FROM valid_qsos "
        "WHERE datetime >= ? AND datetime <= ? ORDER BY datetime",
        (start_db, end_db)
    ).fetchall()]
    conn.close()

    print(f"Loaded {len(all_qsos)} QSOs, {len(region_names)} regions in boundaries")

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {leaflet_turf_head_html()}
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
    {get_controls_html(about_text)}
    {get_legend_html()}
    <script>
        const regionNames = {json.dumps(region_names, indent=8)};
        const boundariesData = {json.dumps(boundaries_data)};
        const allQSOs = {json.dumps(all_qsos, indent=8)};

        let map, isPlaying = false, animationInterval, speed = 1;
        let currentTime = new Date('{contest_start}Z');
        const startTime = new Date('{contest_start}Z');
        const endTime = new Date('{contest_end}Z');
        const regionCoords = {{}};
        let regionLayer;

        {get_legend_js(str(COLOR_THRESHOLDS), str(COLOR_PALETTE), f"QSOs per {region_term}")}

        function playPause() {{
            if (isPlaying) {{
                clearInterval(animationInterval);
                document.getElementById('playBtn').textContent = '▶ Play';
                isPlaying = false;
            }} else {{
                if (currentTime >= endTime) currentTime = new Date(startTime);
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

        function getRegionAbbrev(name) {{
            for (const [abbrev, n] of Object.entries(regionNames)) {{
                if (n === name) return abbrev;
            }}
            return name.substring(0, 3).toUpperCase();
        }}

        function initMap() {{
            map = L.map('map', {{ zoomDelta: 0.25, zoomSnap: 0.25 }}).setView([0, 0], 2);

            // Add county layer first so map always renders even if Turf fails
            regionLayer = L.geoJSON(boundariesData, {{
                style: () => ({{ fillColor: '#e8e8e8', weight: 0.5, opacity: 0.8, color: '#666', fillOpacity: 1.0 }}),
                onEachFeature: function(feature, layer) {{
                    const name = feature.properties.NAME;
                    const abbrev = feature.properties.COUNTY || getRegionAbbrev(name);
                    layer.bindPopup(`<b>${{abbrev}}</b><br>${{name}}<br>QSOs: 0`);
                    layer.regionName = name;
                    layer.regionAbbrev = abbrev;
                }}
            }}).addTo(map);

            map.fitBounds(regionLayer.getBounds());

            // Precompute region centers
            boundariesData.features.forEach(feature => {{
                try {{
                    const name = feature.properties.NAME;
                    const pt = turf.centerOfMass(feature);
                    regionCoords[name] = [pt.geometry.coordinates[1], pt.geometry.coordinates[0]];
                }} catch(e) {{ /* skip */ }}
            }});

            // Turf union for mask/outline — fully optional, map works without it
            try {{
                const allFeatures = boundariesData.features;
                let merged = allFeatures[0];
                for (let i = 1; i < allFeatures.length; i++) {{
                    try {{
                        const u = turf.union(merged, allFeatures[i]);
                        if (u) merged = u;
                    }} catch(e) {{ /* skip this feature */ }}
                }}
                if (merged) {{
                    try {{
                        const mask = turf.difference(turf.bboxPolygon([-180, -90, 180, 90]), merged);
                        if (mask) L.geoJSON(mask, {{
                            style: {{ fillColor: 'white', fillOpacity: 1, weight: 0, stroke: false }},
                            interactive: false, pane: 'overlayPane'
                        }}).addTo(map);
                    }} catch(e) {{ /* mask failed, no worries */ }}
                    L.geoJSON(merged, {{
                        style: {{ fillColor: 'transparent', weight: 3, opacity: 1, color: '#1a252f', fillOpacity: 0 }},
                        interactive: false
                    }}).addTo(map);
                }}
            }} catch(e) {{ console.log('Turf outline skipped:', e); }}

            updateDisplay();
        }}

        function updateDisplay() {{
            document.getElementById('dateDisplay').textContent = currentTime.toISOString().split('T')[0];
            document.getElementById('timeDisplay').textContent = currentTime.toISOString().split('T')[1].substring(0, 5) + 'Z';

            const progress = Math.max(0, Math.min(100, (currentTime - startTime) / (endTime - startTime) * 100));
            document.getElementById('progressBar').style.width = progress + '%';

            const regionQSOs = {{}};
            const regionStations = {{}};
            let totalQSOs = 0;

            allQSOs.forEach(qso => {{
                const t = new Date(qso.t + 'Z');
                if (t >= startTime && t < currentTime) {{
                    const fullName = regionNames[qso.c];
                    if (fullName) {{
                        regionQSOs[fullName] = (regionQSOs[fullName] || 0) + 1;
                        if (!regionStations[fullName]) regionStations[fullName] = {{}};
                        regionStations[fullName][qso.s] = (regionStations[fullName][qso.s] || 0) + 1;
                        totalQSOs++;
                    }}
                }}
            }});

            const maxQSOs = Math.max(0, ...Object.values(regionQSOs));
            updateLegend(maxQSOs);

            regionLayer.eachLayer(layer => {{
                const fullName = layer.regionName;
                const qsoCount = regionQSOs[fullName] || 0;
                layer.setStyle({{ fillColor: getColor(qsoCount, maxQSOs) }});

                let topText = "No activity yet";
                if (regionStations[fullName]) {{
                    topText = Object.entries(regionStations[fullName])
                        .sort((a, b) => b[1] - a[1]).slice(0, 5)
                        .map(([call, n]) => `${{call}}: ${{n}}`).join('<br>');
                }}
                layer.getPopup().setContent(
                    `<b>${{layer.regionAbbrev}}</b><br>${{layer.regionName}}<br>QSOs: ${{qsoCount}}<br><br>Top Stations:<br>${{topText}}`
                );
            }});

            const activeRegions = Object.keys(regionQSOs).length;
            document.getElementById('statusDisplay').textContent =
                `{title} | QSOs: ${{totalQSOs}} | Active {region_term}s: ${{activeRegions}}`;
        }}

        function toggleAbout() {{
            const panel = document.getElementById('aboutPanel');
            if (!panel) return;
            const controls = document.querySelector('.controls');
            if (controls) panel.style.bottom = controls.offsetHeight + 'px';
            panel.classList.toggle('visible');
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
    parser.add_argument('--region-term', default='County', help='Term for host regions (e.g. County, District, Parish)')
    parser.add_argument('--about', default=None, help='About panel text (default: auto-generated from region-term)')
    args = parser.parse_args()

    generate_county_animation(
        args.db, args.boundaries, args.output,
        args.contest_start, args.contest_end, args.title,
        region_term=args.region_term, about_text=args.about
    )


if __name__ == "__main__":
    main()
