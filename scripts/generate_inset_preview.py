#!/usr/bin/env python3
"""
Generate a standalone inset preview page.
Shows each inset as a separate locked Leaflet map so they can be tuned
before embedding in the main enhanced map and county animation.

Usage:
  python scripts/generate_inset_preview.py \
    --meta-db data/bcqp_2026/contest_meta.db \
    --qso-db  data/bcqp_2026/contest_qsos.db \
    --boundaries reference/bc_districts.json \
    --output outputs/bcqp_2026/html/bcqp_2026_inset_preview.html \
    --insets '[{"label":"Victoria & South Island","bounds":[[-123.9,48.28],[-123.05,48.88]]},
               {"label":"Metro Vancouver","bounds":[[-123.45,49.0],[-122.52,49.45]]}]' \
    --title "BCQP 2026 Inset Preview"
"""

import sqlite3
import json
import argparse
from pathlib import Path
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.vendor_assets import leaflet_head_html


def get_county_data(meta_db, qso_db):
    qso_conn = sqlite3.connect(qso_db)
    cursor = qso_conn.execute("""
        SELECT tx_county, tx_call, COUNT(*) as qso_count
        FROM valid_qsos
        WHERE tx_county IS NOT NULL AND tx_county != ''
        GROUP BY tx_county, tx_call
        ORDER BY tx_county, qso_count DESC
    """)
    county_qsos = {}
    county_top = {}
    for county, call, n in cursor.fetchall():
        county = county.upper()
        county_qsos[county] = county_qsos.get(county, 0) + n
        county_top.setdefault(county, []).append({'call': call, 'qsos': n})
    for c in county_top:
        county_top[c] = sorted(county_top[c], key=lambda x: -x['qsos'])[:5]
    qso_conn.close()
    return {
        abbrev: {'qsos': county_qsos[abbrev], 'top5': county_top.get(abbrev, [])}
        for abbrev in county_qsos
    }


def generate_preview(meta_db, qso_db, boundaries_file, insets, output, title):
    with open(boundaries_file) as f:
        boundaries_data = json.load(f)

    name_map = {
        feat['properties']['NAME']: feat['properties']['COUNTY']
        for feat in boundaries_data['features']
        if 'NAME' in feat['properties'] and 'COUNTY' in feat['properties']
    }

    county_data = get_county_data(meta_db, qso_db)

    # Build one map block per inset
    map_divs = []
    map_inits = []

    for i, inset in enumerate(insets):
        b = inset['bounds']   # [[lon_min, lat_min], [lon_max, lat_max]]
        lb = f'[[{b[0][1]},{b[0][0]}],[{b[1][1]},{b[1][0]}]]'
        label = inset['label']

        map_divs.append(f'''
        <div class="inset-panel">
            <div class="inset-title">{label}</div>
            <div class="inset-map" id="imap-{i}"></div>
        </div>''')

        map_inits.append(f'''
        (function() {{
            var lb = {lb};
            var m = L.map('imap-{i}', {{
                dragging: false, touchZoom: false, scrollWheelZoom: false,
                doubleClickZoom: false, boxZoom: false, keyboard: false,
                zoomControl: false, attributionControl: false,
                maxBounds: lb, maxBoundsViscosity: 1.0
            }});

            L.geoJSON(boundaries, {{
                style: function(feature) {{
                    var abbrev = nameMap[feature.properties.NAME];
                    var qsos = countyData[abbrev] ? countyData[abbrev].qsos : 0;
                    return {{ fillColor: getColor(qsos), weight: 1.5, opacity: 0.9,
                              color: '#555', fillOpacity: 0.7 }};
                }},
                onEachFeature: function(feature, layer) {{
                    var cName = feature.properties.NAME;
                    var abbrev = nameMap[cName];
                    var data = countyData[abbrev];
                    var popup = '<div class="popup-content"><div class="popup-title">'
                              + (abbrev || cName) + '</div>';
                    if (data && data.qsos > 0) {{
                        popup += '<div class="popup-qsos">QSOs: ' + data.qsos.toLocaleString() + '</div>';
                        if (data.top5 && data.top5.length) {{
                            popup += '<div><strong>Top Stations:</strong></div>';
                            data.top5.forEach(function(s, j) {{
                                popup += '<div class="callsign-item">'
                                       + '<span><span class="callsign-rank">' + (j+1) + '.</span>'
                                       + '<span class="callsign-call">' + s.call + '</span></span>'
                                       + '<span class="callsign-count">' + s.qsos.toLocaleString() + '</span></div>';
                            }});
                        }}
                    }} else {{
                        popup += '<div class="popup-zero">No QSO activity recorded</div>';
                    }}
                    popup += '</div>';
                    layer.bindPopup(popup, {{autoPan: false}});
                    layer.on({{
                        mouseover: function(e) {{
                            e.target.setStyle({{ weight: 3, color: '#2c3e50', fillOpacity: 0.9 }});
                            e.target.bindTooltip(
                                (abbrev || cName) + (data && data.qsos ? '<br>' + data.qsos.toLocaleString() + ' QSOs' : ''),
                                {{permanent: false, sticky: true}}).openTooltip();
                        }},
                        mouseout: function(e) {{
                            e.target.setStyle({{ weight: 1.5, color: '#555', fillOpacity: 0.7 }});
                            e.target.closeTooltip();
                            e.target.closePopup();
                        }}
                    }});
                }}
            }}).addTo(m);

            m.fitBounds(lb);
        }})();''')

    maps_html  = '\n'.join(map_divs)
    maps_js    = '\n'.join(map_inits)
    n_insets   = len(insets)

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    {leaflet_head_html()}
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; background: #eee; }}
        h2 {{ margin: 0 0 16px; font-size: 18px; color: #2c3e50; }}
        .inset-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
        .inset-panel {{ flex: 1; min-width: 280px; max-width: 520px;
                        background: white; border: 2px solid #2c3e50;
                        border-radius: 4px; overflow: hidden;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2); }}
        .inset-title {{ background: #2c3e50; color: #ecf0f1;
                        font-size: 13px; font-weight: bold;
                        padding: 6px 12px; }}
        .inset-map {{ height: 320px; }}
        .popup-content {{ min-width: 200px; font-size: 14px; }}
        .popup-title {{ font-size: 15px; font-weight: bold; margin-bottom: 8px; }}
        .popup-qsos {{ margin-bottom: 8px; }}
        .popup-zero {{ color: #e74c3c; font-style: italic; }}
        .callsign-item {{ display: flex; justify-content: space-between;
                          padding: 3px 0; border-bottom: 1px solid #ecf0f1; font-size: 13px; }}
        .callsign-rank {{ color: #95a5a6; margin-right: 6px; }}
        .callsign-call {{ font-weight: bold; color: #2980b9; }}
        .callsign-count {{ color: #7f8c8d; }}
        p.note {{ font-size: 12px; color: #666; margin-top: 12px; }}
    </style>
</head>
<body>
    <h2>{title}</h2>
    <div class="inset-row">
{maps_html}
    </div>
    <p class="note">Maps are locked (no pan/zoom). Click a district to see its popup. Hover for tooltip.</p>
    <script>
        const boundaries = {json.dumps(boundaries_data)};
        const countyData = {json.dumps(county_data, indent=2)};
        const nameMap = {json.dumps(name_map, indent=2)};

        const maxQsos = Math.max(0, ...Object.values(countyData).map(d => d.qsos));

        const PCT_BREAKS = [0.05, 0.1, 0.2, 0.4, 0.6, 0.8];
        function roundNice(val) {{
            if (val <= 0) return 0;
            const mag = Math.pow(10, Math.floor(Math.log10(val)));
            return Math.round(val / (mag/2)) * (mag/2);
        }}
        const breaks = PCT_BREAKS.map(t => Math.max(1, roundNice(t * maxQsos)));
        const colors = ['#FED976','#FEB24C','#FD8D3C','#FC4E2A','#E31A1C','#BD0026','#800026'];

        function getColor(qsos) {{
            if (!qsos) return '#e8e8e8';
            for (var i = breaks.length - 1; i >= 0; i--) {{
                if (qsos >= breaks[i]) return colors[i + 1];
            }}
            return colors[0];
        }}

{maps_js}
    </script>
</body>
</html>'''

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w') as f:
        f.write(html)
    print(f"Inset preview saved to {output}")


def main():
    parser = argparse.ArgumentParser(description='Generate standalone inset preview page')
    parser.add_argument('--meta-db',      required=True)
    parser.add_argument('--qso-db',       required=True)
    parser.add_argument('--boundaries',   required=True)
    parser.add_argument('--insets',       required=True,
                        help='JSON array of inset defs: [{"label":"...","bounds":[[lon_min,lat_min],[lon_max,lat_max]]},...]')
    parser.add_argument('--output',       required=True)
    parser.add_argument('--title',        default='Inset Preview')
    args = parser.parse_args()

    insets = json.loads(args.insets)
    generate_preview(args.meta_db, args.qso_db, args.boundaries,
                     insets, args.output, args.title)


if __name__ == '__main__':
    main()
