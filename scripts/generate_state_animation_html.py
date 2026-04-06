#!/usr/bin/env python3
"""
US state-level QSO activity animation.
Shows cumulative QSO counts per state over the contest period.
Requires pre-computed animation data from generate_state_animation_data.py.
"""

import json
import argparse
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.animation_controls import get_controls_html, get_controls_css, get_controls_js
from lib.animation_legend import get_legend_html, get_legend_css, get_legend_js

MAP_CENTER = [39.8, -98.6]
MAP_ZOOM = 4
ANIMATION_SPEEDS = [1, 5, 10, 50]
COLOR_THRESHOLDS = [0, 0.05, 0.15, 0.35, 0.65]
COLOR_PALETTE = ['#f0f0f0', '#d4c5a9', '#f4e4a6', '#f7b32b', '#d73027', '#a50f15']
EXCLUDED_STATES = ['Alaska', 'Hawaii', 'Puerto Rico']
ALASKA_SCALE_FACTOR = 0.44

US_STATE_MAP = {
    'Alabama': 'AL', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL',
    'Georgia': 'GA', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN',
    'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
    'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI',
    'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT',
    'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
    'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND',
    'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
    'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN',
    'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA',
    'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC',
}

US_STATE_CODES = set(US_STATE_MAP.values())


def generate_state_animation_html(animation_data_file, boundaries_file, output_file,
                                   host_state, contest_name, title):
    with open(animation_data_file, 'r') as f:
        animation_data = json.load(f)

    with open(boundaries_file, 'r') as f:
        boundaries_data = json.load(f)

    contest_meta = {'contest_name': contest_name, 'host_state': host_state}

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
        #map {{ height: 100vh; width: 100%; }}
        {get_controls_css()}
        {get_legend_css()}
    </style>
</head>
<body>
    <div id="map"></div>
    {get_controls_html()}
    {get_legend_html()}
    <script>
        const animationData = {json.dumps(animation_data)};
        const boundariesData = {json.dumps(boundaries_data)};
        const contestMeta = {json.dumps(contest_meta)};
        const hostState = '{host_state}';
        const stateMap = {json.dumps(US_STATE_MAP)};
        const excludedStates = {json.dumps(EXCLUDED_STATES)};
        const usStateCodes = {json.dumps(list(US_STATE_CODES))};

        let map, stateLayer;

        {get_controls_js(str(ANIMATION_SPEEDS))}
        {get_legend_js(str(COLOR_THRESHOLDS), str(COLOR_PALETTE), "QSOs per State")}

        map = L.map('map').setView({MAP_CENTER}, {MAP_ZOOM});

        L.tileLayer('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=',
            {{ attribution: '' }}).addTo(map);

        const lower48 = boundariesData.features.filter(f => !excludedStates.includes(f.properties.name || ''));

        stateLayer = L.geoJSON({{ type: "FeatureCollection", features: lower48 }}, {{
            style: getStateStyle,
            onEachFeature: function(feature, layer) {{
                const name = feature.properties.name || 'Unknown';
                layer.bindPopup(`<b>${{name}}</b><br>QSOs: 0`);
            }}
        }}).addTo(map);

        map.fitBounds(stateLayer.getBounds(), {{ padding: [20, 20] }});
        addInsets();

        function getStateStyle(feature) {{
            const code = stateMap[feature.properties.name] || '';
            const frame = animationData.frames[currentFrame];
            const count = (frame && frame.states[code]) || 0;
            return {{ fillColor: getColor(count), weight: 0.5, opacity: 0.8, color: '#666', fillOpacity: 0.7 }};
        }}

        function updateFrame() {{
            const frame = animationData.frames[currentFrame];
            document.getElementById('dateDisplay').textContent = frame.date;
            document.getElementById('timeDisplay').textContent = frame.time + 'Z';
            document.getElementById('progressBar').style.width =
                ((currentFrame / (animationData.frames.length - 1)) * 100) + '%';

            const nonHostValues = Object.entries(frame.states || {{}})
                .filter(([s]) => s !== hostState).map(([, v]) => v);
            const maxQSOs = nonHostValues.length > 0 ? Math.max(...nonHostValues) : 1;

            stateLayer.eachLayer(layer => {{
                const code = stateMap[layer.feature.properties.name] || '';
                const count = (frame.states && frame.states[code]) || 0;
                layer.setStyle({{ fillColor: getColor(count, maxQSOs) }});
                layer.bindPopup(`<b>${{layer.feature.properties.name}}</b><br>QSOs: ${{count}}`);
            }});

            updateLegend(maxQSOs);

            const totalQsos = Object.values(frame.states || {{}}).reduce((s, v) => s + v, 0);
            const activeStates = Object.keys(frame.states || {{}})
                .filter(s => usStateCodes.includes(s) && frame.states[s] > 0).length;
            document.getElementById('statusDisplay').textContent =
                `${{contestMeta.contest_name}} US State Activity | QSOs: ${{totalQsos}} | Active States: ${{activeStates}}`;
        }}

        function addInsets() {{
            const alaskaFeature = boundariesData.features.find(f => f.properties.name === 'Alaska');
            const hawaiiFeature = boundariesData.features.find(f => f.properties.name === 'Hawaii');

            const insetControl = L.control({{ position: 'bottomleft' }});
            insetControl.onAdd = function() {{
                const div = L.DomUtil.create('div', 'insets');
                div.style.marginBottom = '120px';
                div.innerHTML = `
                    <div style="background:white;border:1px solid #666;margin:5px;padding:5px;width:170px;height:140px;box-sizing:border-box;">
                        <div style="font-size:12px;margin-bottom:2px;">Alaska</div>
                        <svg width="162" height="120" viewBox="-84 -75 22 30" preserveAspectRatio="xMidYMid meet">
                            <path d="${{alaskaFeature ? getPathFromCoords(alaskaFeature.geometry.coordinates, true) : ''}}"
                                  fill="#e8e8e8" stroke="#666" stroke-width="0.2"/>
                        </svg>
                    </div>
                    <div style="background:white;border:1px solid #666;margin:5px;padding:5px;width:170px;height:90px;box-sizing:border-box;">
                        <div style="font-size:12px;margin-bottom:2px;">Hawaii</div>
                        <svg width="160" height="80" viewBox="-161 -23 6 6">
                            <path d="${{hawaiiFeature ? getPathFromCoords(hawaiiFeature.geometry.coordinates) : ''}}"
                                  fill="#e8e8e8" stroke="#666" stroke-width="0.1"/>
                        </svg>
                    </div>`;
                return div;
            }};
            insetControl.addTo(map);
        }}

        function getPathFromCoords(coords, isAlaska = false) {{
            if (!coords || !coords.length) return '';
            const scale = {ALASKA_SCALE_FACTOR};
            const paths = [];
            const processRing = ring => {{
                return 'M' + ring.map(p => isAlaska
                    ? (p[0]*scale) + ',' + (-p[1])
                    : p[0] + ',' + (-p[1])
                ).join('L') + 'Z';
            }};
            if (Array.isArray(coords[0][0][0])) {{
                coords.forEach(poly => poly.forEach(ring => paths.push(processRing(ring))));
            }} else {{
                coords.forEach(ring => paths.push(processRing(ring)));
            }}
            return paths.join(' ');
        }}

        updateFrame();
    </script>
</body></html>'''

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(html)
    print(f"State animation saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate US state-level QSO animation')
    parser.add_argument('--animation-data', required=True,
                        help='Path to state_qso_animation_data.json (from generate_state_animation_data.py)')
    parser.add_argument('--boundaries', required=True,
                        help='Path to US states GeoJSON boundaries file')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--host-state', default='NY', help='Host state abbreviation')
    parser.add_argument('--contest-name', required=True,
                        help='Contest display name (e.g. "2025 New York QSO Party")')
    parser.add_argument('--title', help='HTML page title (defaults to contest-name)')
    args = parser.parse_args()

    generate_state_animation_html(
        args.animation_data, args.boundaries, args.output,
        args.host_state, args.contest_name,
        args.title or args.contest_name
    )


if __name__ == "__main__":
    main()
