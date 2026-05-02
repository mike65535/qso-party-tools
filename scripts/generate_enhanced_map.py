#!/usr/bin/env python3
"""
Generate enhanced interactive county-level QSO activity map.
Choropleth with hover tooltips and click popups showing top stations per county.

Requires a GeoJSON boundaries file for the host state (default: reference/ny_counties.json).

Optional inset panels: pass --insets as a JSON array of dicts, each with:
  label   — panel header text
  bounds  — [[lon_min, lat_min], [lon_max, lat_max]]  source area (GeoJSON/lon-first)
  target  — [[lon_min, lat_min], [lon_max, lat_max]]  display area on main map
             (like AK/HI in the state animation — features are coordinate-transformed
              and rendered as a layer on the main map, panning/zooming naturally)
"""

import sqlite3
import json
import argparse
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.vendor_assets import leaflet_head_html


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


MAP_ABOUT = (
    "This map shows total QSO activity by region for the entire contest period. "
    "Region color reflects the number of QSOs logged by stations operating from that region; "
    "hover over a region for a quick summary or click for the top stations. "
    "Regions with no submitted logs appear in gray even if they were worked by other stations. "
    "The color scale uses seven bands relative to the region with the highest QSO total."
)


_INSET_W       = 280
_INSET_MAP_H   = 200
_INSET_LABEL_H = 26
_INSET_PANEL_H = _INSET_MAP_H + _INSET_LABEL_H
_INSET_GAP     = 10
_INSET_BOTTOM  = 70   # above the 50px footer bar


def _inset_css():
    return f'''
        .inset-panel {{
            position: fixed; left: 10px; z-index: 1000;
            width: {_INSET_W}px;
            border: 2px solid #2c3e50; border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .inset-title {{
            background: #2c3e50; color: #ecf0f1;
            font-size: 12px; font-weight: bold;
            padding: 4px 10px; height: {_INSET_LABEL_H}px;
            line-height: {_INSET_LABEL_H - 8}px; box-sizing: border-box;
        }}
        .inset-map {{ height: {_INSET_MAP_H}px; width: 100%; background: white; overflow: hidden; clip-path: inset(0); }}
        .inset-map .leaflet-tooltip {{ max-width: 160px; white-space: normal; line-height: 1.25; }}'''


def _inset_divs(insets):
    if not insets:
        return ''
    parts = []
    for i, inset in enumerate(insets):
        bottom = _INSET_BOTTOM + i * (_INSET_PANEL_H + _INSET_GAP)
        parts.append(
            f'    <div class="inset-panel" style="bottom:{bottom}px">'
            f'<div class="inset-title">{inset["label"]}</div>'
            f'<div class="inset-map" id="inset-map-{i}"></div></div>'
        )
    return '\n'.join(parts)


def _inset_js(insets):
    if not insets:
        return ''
    blocks = []
    for i, inset in enumerate(insets):
        b = inset['bounds']
        lb = f'[[{b[0][1]},{b[0][0]}],[{b[1][1]},{b[1][0]}]]'
        blocks.append(f'''
        (function() {{
            var lb = {lb};
            var im = L.map('inset-map-{i}', {{
                dragging: false, touchZoom: false, scrollWheelZoom: false,
                doubleClickZoom: false, boxZoom: false, keyboard: false,
                zoomControl: false, attributionControl: false,
                maxBounds: lb, maxBoundsViscosity: 1.0
            }});
            L.geoJSON(boundaries, {{
                style: function(feature) {{
                    var abbrev = nameMap[feature.properties.NAME];
                    var qsos = countyData[abbrev] ? countyData[abbrev].qsos : 0;
                    return {{ fillColor: getColor(qsos), weight: 1.5, opacity: 0.9, color: '#555', fillOpacity: 0.7 }};
                }},
                onEachFeature: function(feature, layer) {{
                    var cName = feature.properties.NAME;
                    var abbrev = nameMap[cName];
                    var data = countyData[abbrev];
                    var dname = cName.replace(/\u2014/g, ' ');
                    var tip = '<b>'+(abbrev||cName)+'</b><br>'+dname;
                    if (data && data.qsos > 0) {{
                        tip += '<br>QSOs: '+data.qsos.toLocaleString();
                        if (data.top5 && data.top5.length) {{
                            tip += '<br>'+data.top5.map(function(s,j){{return (j+1)+'. '+s.call+': '+s.qsos;}}).join('<br>');
                        }}
                    }} else {{
                        tip += '<br>No activity';
                    }}
                    layer.bindTooltip(tip, {{permanent: false, sticky: true, direction: 'top'}});
                    layer.on({{
                        mouseover: function(e) {{
                            e.target.setStyle({{ weight: 3, color: '#2c3e50', fillOpacity: 0.9 }});
                            e.target.openTooltip();
                        }},
                        mousemove: function(e) {{
                            var tt = e.target.getTooltip();
                            if (!tt) return;
                            var rect = document.getElementById('inset-map-{i}').getBoundingClientRect();
                            var cx = e.originalEvent.clientX, cy = e.originalEvent.clientY;
                            var dTop = cy - rect.top, dBottom = rect.bottom - cy;
                            var dLeft = cx - rect.left, dRight = rect.right - cx;
                            var m = Math.min(dTop, dBottom, dLeft, dRight);
                            tt.options.direction = m === dTop ? 'bottom' : m === dBottom ? 'top' : m === dLeft ? 'right' : 'left';
                        }},
                        mouseout: function(e) {{
                            e.target.setStyle({{ weight: 1.5, color: '#555', fillOpacity: 0.7 }});
                            e.target.closeTooltip();
                        }}
                    }});
                }}
            }}).addTo(im);
            im.fitBounds(lb);
        }})();''')
    return '\n'.join(blocks)


def generate_map_html(meta_db, qso_db, boundaries_file, title, valid_counties, name_map,
                      map_about=MAP_ABOUT, insets=None, region_term='County'):
    """Generate the complete HTML map file."""
    county_qsos, county_top_stations, total_qsos = get_county_data(meta_db, qso_db, valid_counties)

    county_data = {
        abbrev: {"qsos": qso_count, "top5": county_top_stations.get(abbrev, [])}
        for abbrev, qso_count in county_qsos.items()
    }

    total_qsos_by_county = sum(county_qsos.values())
    active_counties = len(county_qsos)
    num_counties = len(valid_counties) if valid_counties else '?'
    print(f"Total QSOs in database: {total_qsos}")
    print(f"QSOs from host-state counties: {total_qsos_by_county}")
    print(f"Active counties: {active_counties}")

    try:
        with open(boundaries_file, 'r') as f:
            boundaries_data = json.load(f)
        boundaries_json = json.dumps(boundaries_data)
        print(f"Loaded boundaries from {boundaries_file}")
    except Exception as e:
        print(f"WARNING: Could not load boundaries ({e}) — map will have no county shapes")
        boundaries_data = None
        boundaries_json = '{"type": "FeatureCollection", "features": []}'

    rt = region_term
    rts = f'{region_term}s'
    inset_css  = _inset_css()        if insets else ''
    inset_divs = _inset_divs(insets)
    inset_js   = _inset_js(insets)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    {leaflet_head_html()}
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; background: white; }}
        #map {{ position: absolute; top: 0; bottom: 50px; left: 0; right: 0; background: white; }}
        #info {{ position: absolute; bottom: 0; left: 0; right: 0; height: 50px; background: #2c3e50; color: white; padding: 0 15px; display: flex; align-items: center; justify-content: center; z-index: 1000; font-size: 16px; }}
        #info-text {{ flex: 1; text-align: center; }}
        #about-btn {{ background: #3498db; color: white; border: none; padding: 5px 11px; border-radius: 4px; cursor: pointer; font-size: 13px; white-space: nowrap; }}
        #about-btn:hover {{ background: #2980b9; }}
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
        #map-legend {{ position: fixed; top: 10px; right: 10px; z-index: 9999;
                       background: white; padding: 10px 14px; border-radius: 6px;
                       box-shadow: 0 1px 5px rgba(0,0,0,0.3); line-height: 1.6;
                       font-size: 13px; min-width: 160px; }}
        #map-legend h4 {{ margin: 0 0 6px 0; font-size: 13px; color: #333; }}
        .map-legend-item {{ display: flex; align-items: center; gap: 8px; margin: 2px 0; }}
        .map-legend-swatch {{ width: 18px; height: 18px; border: 1px solid #aaa;
                              flex-shrink: 0; border-radius: 2px; }}
        #about-panel {{ display: none; position: fixed; bottom: 50px; left: 0; right: 0;
                        background: rgba(44,62,80,0.96); color: #ecf0f1;
                        padding: 14px 48px 14px 20px; font-size: 13px; line-height: 1.6; z-index: 9998; }}
        #about-panel.visible {{ display: block; }}
        #about-close {{ position: absolute; top: 8px; right: 12px; background: none; border: none;
                        color: #ecf0f1; font-size: 18px; cursor: pointer; }}{inset_css}
    </style>
</head>
<body>
    <div id="map"><div id="map-legend"><h4>QSOs per {rt}</h4></div></div>
{inset_divs}
    <div id="about-panel">{map_about}<button id="about-close" onclick="toggleAbout()">&#x2715;</button></div>
    <div id="info">
        <span id="info-text">{title} | {total_qsos_by_county:,} QSOs from {active_counties} of {num_counties} {rts}</span>
        <button id="about-btn" onclick="toggleAbout()">&#x2139; About</button>
    </div>
    <script>
        const boundaries = {boundaries_json};
        const countyData = {json.dumps(county_data, indent=2)};
        const nameMap = {json.dumps(name_map, indent=2)};

        const map = L.map('map', {{
            zoomControl: true, scrollWheelZoom: true, doubleClickZoom: true,
            boxZoom: true, keyboard: true, dragging: true, minZoom: 6, maxZoom: 11
        }});

        const maxQsos = Math.max(...Object.values(countyData).map(d => d.qsos));

        function roundNice(val) {{
            if (val <= 0) return 0;
            const mag = Math.pow(10, Math.floor(Math.log10(val)));
            const step = mag / 2;
            return Math.round(val / step) * step;
        }}

        const PCT_BREAKS = [0.05, 0.1, 0.2, 0.4, 0.6, 0.8];
        const breaks = PCT_BREAKS.map(t => Math.max(1, roundNice(t * maxQsos)));
        const colors = ['#FED976','#FEB24C','#FD8D3C','#FC4E2A','#E31A1C','#BD0026','#800026'];

        function getColor(qsos) {{
            if (qsos === 0) return '#e8e8e8';
            for (let i = breaks.length - 1; i >= 0; i--) {{
                if (qsos >= breaks[i]) return colors[i + 1];
            }}
            return colors[0];
        }}

        L.geoJSON(boundaries, {{
            style: function(feature) {{
                const abbrev = nameMap[feature.properties.NAME];
                const qsos = countyData[abbrev] ? countyData[abbrev].qsos : 0;
                return {{ fillColor: getColor(qsos), weight: 1.5, opacity: 0.9, color: '#555', fillOpacity: 0.7 }};
            }},
            onEachFeature: function(feature, layer) {{
                const countyName = feature.properties.NAME;
                const abbrev = nameMap[countyName];
                const data = countyData[abbrev];

                let popup = `<div class="popup-content"><div class="popup-title">${{abbrev}} \u2014 ${{countyName}}</div>`;
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
                        e.target.bindTooltip(`${{abbrev}} \u2014 ${{countyName}}<br>${{qsoCount}} QSOs`,
                            {{ permanent: false, direction: 'top' }}).openTooltip();
                    }},
                    mouseout: function(e) {{
                        e.target.setStyle({{ weight: 1.5, color: '#555', fillOpacity: 0.7 }});
                        e.target.closeTooltip();
                        e.target.closePopup();
                    }}
                }});
            }}
        }}).addTo(map);

        map.fitBounds(L.geoJSON(boundaries).getBounds(), {{padding: [30, 30]}});

        function toggleAbout() {{
            document.getElementById('about-panel').classList.toggle('visible');
        }}

        // Legend
        const legendDiv = document.getElementById('map-legend');
        legendDiv.innerHTML += `<div class="map-legend-item">
            <div class="map-legend-swatch" style="background:${{colors[6]}}"></div>
            <span>&gt; ${{breaks[5].toLocaleString()}}</span></div>`;
        for (let i = 4; i >= 0; i--) {{
            legendDiv.innerHTML += `<div class="map-legend-item">
                <div class="map-legend-swatch" style="background:${{colors[i+1]}}"></div>
                <span>${{breaks[i].toLocaleString()}} \u2013 ${{(breaks[i+1]-1).toLocaleString()}}</span></div>`;
        }}
        legendDiv.innerHTML += `<div class="map-legend-item">
            <div class="map-legend-swatch" style="background:${{colors[0]}}"></div>
            <span>1 \u2013 ${{(breaks[0]-1).toLocaleString()}}</span></div>`;
        legendDiv.innerHTML += `<div class="map-legend-item">
            <div class="map-legend-swatch" style="background:#e8e8e8"></div>
            <span>No activity</span></div>`;
{inset_js}
    </script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Generate enhanced county activity map')
    parser.add_argument('--meta-db', required=True, help='Path to contest_meta.db')
    parser.add_argument('--qso-db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    parser.add_argument('--boundaries', default='reference/ny_counties.json',
                        help='GeoJSON boundaries file')
    parser.add_argument('--name-map', help='JSON file mapping region names to abbreviations (derived from boundaries if omitted)')
    parser.add_argument('--title', default='QSOs made from host-state stations')
    parser.add_argument('--about', default=MAP_ABOUT, help='About panel text')
    parser.add_argument('--region-term', default='County', help='Display term for regions (e.g. County, District)')
    parser.add_argument('--insets', default=None,
                        help='JSON array of inset definitions: [{"label":"...","bounds":[[lon_min,lat_min],[lon_max,lat_max]],"target":[[lon_min,lat_min],[lon_max,lat_max]]},...]')
    args = parser.parse_args()

    if args.name_map:
        with open(args.name_map, 'r') as f:
            name_map = json.load(f)
    else:
        with open(args.boundaries, 'r') as f:
            bdata = json.load(f)
        name_map = {
            feat['properties']['NAME']: feat['properties']['COUNTY']
            for feat in bdata['features']
            if 'NAME' in feat['properties'] and 'COUNTY' in feat['properties']
        }

    insets = json.loads(args.insets) if args.insets else None

    valid_counties = set(name_map.values())

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    html = generate_map_html(
        args.meta_db, args.qso_db, args.boundaries,
        args.title, valid_counties, name_map, args.about,
        insets=insets, region_term=args.region_term,
    )

    with open(args.output, 'w') as f:
        f.write(html)
    print(f"Enhanced map saved to {args.output}")


if __name__ == "__main__":
    main()
