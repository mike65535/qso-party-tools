#!/usr/bin/env python3
"""
Mobile station QSO activity animation.
Shows mobile stations moving across counties with county-line period detection.
"""

import json
import sqlite3
import argparse
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.animation_controls import get_controls_css
from lib.animation_legend import get_legend_css

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

DEFAULT_ICONS = {
    'N2CU': '🚗', 'K2A': '🚙', 'N2T': '🚐', 'K2V': '🚛', 'KQ2R': '🏎️',
    'KV2X': '🚓', 'N1GBE': '🚑', 'N2B': '🚒', 'AB1BL': '🚌', 'W1WV': '🛻',
    'WI2M': '🚜', 'WT2X': '🏍️',
}


def generate_mobile_animation(qso_db, mobiles_json, county_line_json,
                               boundaries_file, output_file,
                               contest_start, contest_end, title):
    with open(boundaries_file, 'r') as f:
        boundaries_data = json.load(f)

    with open(county_line_json, 'r') as f:
        county_line_periods = json.load(f)

    with open(mobiles_json, 'r') as f:
        mobile_info = json.load(f)
    mobile_callsigns = list(mobile_info.keys())

    conn = sqlite3.connect(qso_db)
    mobile_data = {}
    for callsign in mobile_callsigns:
        cursor = conn.execute("""
            SELECT datetime, tx_county, freq, mode
            FROM qsos WHERE station_call = ? ORDER BY datetime
        """, (callsign,))
        mobile_data[callsign] = [
            {'timestamp': r[0].replace(' ', 'T'), 'county': r[1], 'freq': r[2], 'mode': r[3]}
            for r in cursor.fetchall()
        ]
    conn.close()

    mobile_icons = {call: info.get('icon', DEFAULT_ICONS.get(call, '📍'))
                    for call, info in mobile_info.items()}

    print(f"Loaded {len(mobile_callsigns)} mobile stations")

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
        .mobile-marker {{ background: none; border: none; }}
        .mobile-icon {{ font-size: 20px; text-align: center; line-height: 20px; }}
        .mobile-label {{ font-size: 10px; font-weight: bold; text-align: center; color: #000; text-shadow: 1px 1px 1px white; }}
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="legend" id="legend">
        <div style="font-weight:bold;margin-bottom:5px;">Mobile QSOs</div>
        <div class="legend-item"><div class="legend-color" style="background:#e8e8e8;"></div><span>0</span></div>
    </div>

    <div class="controls">
        <div class="top-controls">
            <button class="control-btn" id="playBtn" onclick="togglePlay()">▶ Play</button>
            <button class="control-btn" onclick="resetAnimation()">⏮ Reset</button>
            <button class="control-btn" id="speedBtn" onclick="cycleSpeed()">Speed 5x</button>
        </div>
        <div class="middle-row">
            <div class="time-info">
                <span id="dateDisplay">--</span> <span id="timeDisplay">--:--Z</span>
            </div>
            <div class="progress-section">
                <div class="progress-container" onclick="seekToPosition(event)">
                    <div class="progress-bar" id="progressBar"></div>
                </div>
            </div>
        </div>
        <div class="bottom-info">
            <span id="statusDisplay">{title} | QSOs: 0 | Counties Covered: 0</span>
        </div>
    </div>

    <script>
        const mobileData = {json.dumps(mobile_data, indent=8)};
        const countyLinePeriods = {json.dumps(county_line_periods, indent=8)};
        const countyNames = {json.dumps(NY_COUNTY_NAMES, indent=8)};
        const mobileIcons = {json.dumps(mobile_icons, indent=8)};
        const boundariesData = {json.dumps(boundaries_data)};

        let map, mobileMarkers = {{}}, isPlaying = false, animationInterval;
        let currentTime = new Date('{contest_start}Z');
        const startTime = new Date('{contest_start}Z');
        const endTime = new Date('{contest_end}Z');
        const countyCoords = {{}};
        let countyLayer;

        const speedMultipliers = [5, 25, 50, 250];
        let speedIdx = 0;
        let speedMultiplier = speedMultipliers[speedIdx];

        function getCountyAbbrev(fullName) {{
            for (const [abbrev, name] of Object.entries(countyNames)) {{
                if (name === fullName + " County") return abbrev;
            }}
            return fullName.substring(0, 3).toUpperCase();
        }}

        function getCountyColor(qsoCount, maxCount) {{
            if (qsoCount === 0 || maxCount === 0) return '#e8e8e8';
            const r = qsoCount / maxCount;
            if (r <= 0.2) return '#ffff99';
            if (r <= 0.4) return '#d4a574';
            if (r <= 0.6) return '#ff8c42';
            if (r <= 0.8) return '#ff4444';
            return '#cc0000';
        }}

        function updateLegend(maxQSOs) {{
            const legend = document.getElementById('legend');
            if (maxQSOs === 0) {{
                legend.innerHTML = '<div style="font-weight:bold;margin-bottom:5px;">Mobile QSOs</div>' +
                    '<div class="legend-item"><div class="legend-color" style="background:#e8e8e8;"></div><span>0</span></div>';
                return;
            }}
            const ranges = [
                {{ color: '#e8e8e8', label: '0' }},
                {{ color: '#ffff99', label: `1-${{Math.ceil(maxQSOs*0.2)}}` }},
                {{ color: '#d4a574', label: `${{Math.ceil(maxQSOs*0.2)+1}}-${{Math.ceil(maxQSOs*0.4)}}` }},
                {{ color: '#ff8c42', label: `${{Math.ceil(maxQSOs*0.4)+1}}-${{Math.ceil(maxQSOs*0.6)}}` }},
                {{ color: '#ff4444', label: `${{Math.ceil(maxQSOs*0.6)+1}}-${{Math.ceil(maxQSOs*0.8)}}` }},
                {{ color: '#cc0000', label: `${{Math.ceil(maxQSOs*0.8)+1}}-${{maxQSOs}}` }},
            ];
            legend.innerHTML = '<div style="font-weight:bold;margin-bottom:5px;">Mobile QSOs</div>' +
                ranges.map(r => `<div class="legend-item"><div class="legend-color" style="background:${{r.color}};"></div><span>${{r.label}}</span></div>`).join('');
        }}

        function getStationCoords(callsign, time) {{
            const periods = countyLinePeriods[callsign] || [];
            for (const period of periods) {{
                const ps = new Date(period.start_time + 'Z'), pe = new Date(period.end_time + 'Z');
                if (time >= ps && time <= pe) {{
                    const c1 = countyCoords[countyNames[period.counties[0]]] || [42.9, -75.5];
                    const c2 = countyCoords[countyNames[period.counties[1]]] || [42.9, -75.5];
                    return [(c1[0]+c2[0])/2, (c1[1]+c2[1])/2];
                }}
            }}
            if (periods.length > 0) {{
                let last = null;
                for (const p of periods) {{ if (time >= new Date(p.start_time + 'Z')) last = p; }}
                if (last) {{
                    const c1 = countyCoords[countyNames[last.counties[0]]] || [42.9, -75.5];
                    const c2 = countyCoords[countyNames[last.counties[1]]] || [42.9, -75.5];
                    return [(c1[0]+c2[0])/2, (c1[1]+c2[1])/2];
                }}
            }}
            const qsos = mobileData[callsign] || [];
            let county = null;
            for (const q of qsos) {{ if (new Date(q.timestamp + 'Z') <= time) county = q.county; else break; }}
            if (!county && qsos.length > 0) county = qsos[0].county;
            if (county) {{
                const base = countyCoords[countyNames[county]] || [42.9, -75.5];
                const idx = Object.keys(mobileData).indexOf(callsign);
                return [base[0] + (idx%3-1)*0.05, base[1] + (Math.floor(idx/3)%3-1)*0.05];
            }}
            return [42.9, -75.5];
        }}

        function isOnCountyLine(callsign, time) {{
            for (const p of (countyLinePeriods[callsign] || [])) {{
                if (time >= new Date(p.start_time + 'Z') && time <= new Date(p.end_time + 'Z'))
                    return {{ isCountyLine: true, counties: p.counties }};
            }}
            return {{ isCountyLine: false, counties: [] }};
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
                style: () => ({{ fillColor: '#e8e8e8', weight: 0.5, opacity: 0.8, color: '#666', fillOpacity: 0.7 }}),
                onEachFeature: function(feature, layer) {{
                    const name = feature.properties.NAME;
                    layer.countyName = name;
                    layer.countyAbbrev = getCountyAbbrev(name);
                    layer.bindPopup(`<b>${{layer.countyAbbrev}}</b><br>${{name}} County<br>Mobile QSOs: 0`);
                }}
            }}).addTo(map);

            if (merged) {{
                try {{
                    const mask = turf.difference(turf.bboxPolygon([-180,-90,180,90]), merged);
                    if (mask) L.geoJSON(mask, {{
                        style: {{ fillColor:'white', fillOpacity:1, weight:0, stroke:false }},
                        interactive: false, pane:'overlayPane'
                    }}).addTo(map);
                }} catch(e) {{}}
                L.geoJSON(merged, {{
                    style: {{ fillColor:'transparent', weight:3, opacity:1, color:'#1a252f', fillOpacity:0 }},
                    interactive: false
                }}).addTo(map);
            }}

            boundariesData.features.forEach(feature => {{
                const name = feature.properties.NAME;
                const bbox = turf.bbox(feature);
                countyCoords[name + " County"] = [(bbox[1]+bbox[3])/2, (bbox[0]+bbox[2])/2];
            }});

            // Create mobile markers
            for (const [call, qsos] of Object.entries(mobileData)) {{
                if (!qsos.length) continue;
                const iconSymbol = mobileIcons[call] || '📍';
                const icon = L.divIcon({{
                    html: `<div class="mobile-icon">${{iconSymbol}}</div><div class="mobile-label">${{call}}</div>`,
                    className: 'mobile-marker', iconSize: [20,20], iconAnchor: [10,10]
                }});
                const marker = L.marker(getStationCoords(call, currentTime), {{ icon, riseOnHover: true }});
                marker.bindPopup(`<b>${{call}}</b><br>Initializing...`);
                mobileMarkers[call] = marker;
                marker.addTo(map);
                marker.setOpacity(0);
            }}

            updateDisplay();
        }}

        function updateDisplay() {{
            document.getElementById('dateDisplay').textContent = currentTime.toISOString().split('T')[0];
            document.getElementById('timeDisplay').textContent = currentTime.toISOString().split('T')[1].substring(0,5) + 'Z';
            const progress = Math.max(0, Math.min(100, (currentTime-startTime)/(endTime-startTime)*100));
            document.getElementById('progressBar').style.width = progress + '%';

            const countyQSOs = {{}};
            let totalQSOs = 0;
            const countiesCovered = new Set();

            for (const [call, qsos] of Object.entries(mobileData)) {{
                const marker = mobileMarkers[call];
                if (!marker) continue;

                let currentQSO = null;
                for (const q of qsos) {{
                    if (new Date(q.timestamp + 'Z') <= currentTime) currentQSO = q; else break;
                }}

                if (currentQSO) {{
                    marker.setLatLng(getStationCoords(call, currentTime));
                    marker.setOpacity(1);
                    const det = isOnCountyLine(call, currentTime);
                    const countyDisplay = det.isCountyLine ? det.counties.join('/') : currentQSO.county;
                    const qsoCount = qsos.filter(q => new Date(q.timestamp+'Z') < currentTime).length;
                    marker.getPopup().setContent(`<b>${{call}}</b><br>County: ${{countyDisplay}}<br>QSOs: ${{qsoCount}}`);
                }} else {{
                    marker.setOpacity(0);
                }}
            }}

            Object.values(mobileData).forEach(qsos => {{
                qsos.forEach(q => {{
                    if (new Date(q.timestamp+'Z') < currentTime) {{
                        const fullName = countyNames[q.county];
                        if (fullName) {{ countyQSOs[fullName] = (countyQSOs[fullName]||0)+1; countiesCovered.add(q.county); totalQSOs++; }}
                    }}
                }});
            }});

            const maxQSOs = Math.max(0, ...Object.values(countyQSOs));
            updateLegend(maxQSOs);

            countyLayer.eachLayer(layer => {{
                const fullName = layer.countyName + " County";
                const qsoCount = countyQSOs[fullName] || 0;
                layer.setStyle({{ fillColor: getCountyColor(qsoCount, maxQSOs) }});
                layer.getPopup().setContent(`<b>${{layer.countyAbbrev}}</b><br>${{layer.countyName}} County<br>Mobile QSOs: ${{qsoCount}}`);
            }});

            document.getElementById('statusDisplay').textContent =
                `{title} | QSOs: ${{totalQSOs}} | Counties Covered: ${{countiesCovered.size}}`;
        }}

        function togglePlay() {{
            if (isPlaying) {{
                clearInterval(animationInterval);
                document.getElementById('playBtn').textContent = '▶ Play';
                isPlaying = false;
            }} else {{
                animationInterval = setInterval(() => {{
                    currentTime = new Date(currentTime.getTime() + 60000);
                    if (currentTime > endTime) {{ currentTime = endTime; togglePlay(); }}
                    updateDisplay();
                }}, 1000 / speedMultiplier);
                document.getElementById('playBtn').textContent = '⏸ Pause';
                isPlaying = true;
            }}
        }}

        function resetAnimation() {{
            if (isPlaying) togglePlay();
            currentTime = new Date('{contest_start}Z');
            Object.values(mobileMarkers).forEach(m => m.setOpacity(0));
            updateDisplay();
        }}

        function cycleSpeed() {{
            speedIdx = (speedIdx + 1) % speedMultipliers.length;
            speedMultiplier = speedMultipliers[speedIdx];
            document.getElementById('speedBtn').textContent = `Speed ${{speedMultiplier}}x`;
            if (isPlaying) {{ clearInterval(animationInterval); togglePlay(); togglePlay(); }}
        }}

        function seekToPosition(event) {{
            const rect = event.currentTarget.getBoundingClientRect();
            const pct = (event.clientX - rect.left) / rect.width;
            currentTime = new Date(startTime.getTime() + pct * (endTime - startTime));
            updateDisplay();
        }}

        document.addEventListener('DOMContentLoaded', initMap);
    </script>
</body></html>'''

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(html)
    print(f"Mobile animation saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate mobile station QSO animation')
    parser.add_argument('--db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--mobiles', required=True, help='Path to mobile_stations.json')
    parser.add_argument('--county-line-periods', required=True, help='Path to county_line_periods.json')
    parser.add_argument('--boundaries', default='reference/ny_counties.json')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--contest-start', required=True,
                        help='Contest start UTC (e.g. "2025-10-18T14:00:00")')
    parser.add_argument('--contest-end', required=True,
                        help='Contest end UTC (e.g. "2025-10-19T02:00:00")')
    parser.add_argument('--title', default='Mobile Station Activity Animation')
    args = parser.parse_args()

    generate_mobile_animation(
        args.db, args.mobiles, args.county_line_periods,
        args.boundaries, args.output,
        args.contest_start, args.contest_end, args.title
    )


if __name__ == "__main__":
    main()
