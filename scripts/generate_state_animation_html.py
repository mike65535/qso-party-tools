#!/usr/bin/env python3
"""
US state / Canadian province QSO activity animation.
AK, HI, and Canadian provinces are repositioned at fake coordinates so they
pan and zoom with the main map rather than fighting as fixed overlays.
"""

import copy
import json
import argparse
import sys
import os
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from lib.animation_controls import get_controls_html, get_controls_css, get_controls_js
from lib.animation_legend import get_legend_html, get_legend_css, get_legend_js
from lib.vendor_assets import leaflet_head_html

ANIMATION_SPEEDS = [1, 2, 5, 10, 20, 50]
COLOR_THRESHOLDS = [0, 0.05, 0.15, 0.35, 0.65]
COLOR_PALETTE = ['#f0f0f0', '#d4c5a9', '#f4e4a6', '#f7b32b', '#d73027', '#a50f15']
EXCLUDED_STATES = ['Alaska', 'Hawaii', 'Puerto Rico']

# Canadian provinces/territories to include
CANADA_PROVINCE_MAP = {
    'Alberta': 'AB', 'British Columbia': 'BC', 'Manitoba': 'MB',
    'New Brunswick': 'NB', 'Newfoundland and Labrador': 'NL',
    'Northwest Territories': 'NT', 'Nova Scotia': 'NS', 'Nunavut': 'NU',
    'Ontario': 'ON', 'Prince Edward Island': 'PE', 'Quebec': 'QC',
    'Saskatchewan': 'SK', 'Yukon Territory': 'YT',
}

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

STATE_ABOUT = (
    "This animation shows cumulative QSO activity by US state over the contest period. "
    "A state or province lights up when any logged station records a QSO with a station from that location — "
    "so they appear even if no log was submitted. "
    "Alaska and Hawaii are repositioned below the continental US at reduced scale; "
    "Canadian provinces are shown above the US border, compressed north-south — "
    "all three move and zoom with the main map. "
    "The color scale is relative to the current frame maximum (excluding the host state) "
    "and adjusts as the contest progresses."
)

# ── Coordinate transformation helpers ────────────────────────────────────────

def _xform_coords(geometry, fn):
    """Apply fn(lon, lat) -> [lon, lat] to every point in a GeoJSON geometry."""
    def xf_ring(ring):
        return [fn(p[0], p[1]) + list(p[2:]) for p in ring]
    def xf_poly(poly):
        return [xf_ring(r) for r in poly]
    coords = geometry['coordinates']
    t = geometry['type']
    if t == 'Polygon':
        return {**geometry, 'coordinates': xf_poly(coords)}
    elif t == 'MultiPolygon':
        return {**geometry, 'coordinates': [xf_poly(p) for p in coords]}
    return geometry

def _xform_feature(feature, fn, extra_props=None):
    f = copy.deepcopy(feature)
    f['geometry'] = _xform_coords(f['geometry'], fn)
    if extra_props:
        f['properties'] = {**f.get('properties', {}), **extra_props}
    return f

def _strip_small_polygons(feature, min_bbox_area=0.5):
    """Remove small polygon parts from a MultiPolygon (reduces Arctic island clutter).
    min_bbox_area is in square degrees of the original coordinates."""
    geom = feature['geometry']
    if geom['type'] != 'MultiPolygon':
        return feature
    def bbox_area(poly):
        ring = poly[0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return (max(lons) - min(lons)) * (max(lats) - min(lats))
    kept = [p for p in geom['coordinates'] if bbox_area(p) >= min_bbox_area]
    if not kept:
        kept = [max(geom['coordinates'], key=bbox_area)]  # always keep at least one
    f = copy.deepcopy(feature)
    if len(kept) == 1:
        f['geometry'] = {'type': 'Polygon', 'coordinates': kept[0]}
    else:
        f['geometry'] = {'type': 'MultiPolygon', 'coordinates': kept}
    return f

def _label_pos(geometry):
    """Return [lon, lat] bbox-center of the largest polygon in the geometry.
    More reliable than the geometric centroid for oddly-shaped regions."""
    def bbox_area(ring):
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return (max(lons) - min(lons)) * (max(lats) - min(lats))
    def bbox_center(ring):
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return [(min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2]
    coords = geometry['coordinates']
    if geometry['type'] == 'Polygon':
        return bbox_center(coords[0])
    elif geometry['type'] == 'MultiPolygon':
        best = max(coords, key=lambda p: bbox_area(p[0]))
        return bbox_center(best[0])
    return None

def _ak_xform(lon, lat):
    if lon > 0:
        lon -= 360  # Aleutians that cross the antimeridian
    return [-117.0 + (lon + 153.0) * 0.35, 26.0 + (lat - 64.0) * 0.35]

def _hi_xform(lon, lat):
    return [-100.0 + (lon + 157.0), 25.0 + (lat - 20.5)]

def _canada_xform(lon, lat):
    return [-96.0 + (lon + 96.0) * 0.7, 53.0 + (lat - 60.0) * 0.35]

def _build_inset_features(boundaries_data, canada_data):
    insets = []
    for feat in boundaries_data['features']:
        name = feat['properties'].get('name', '')
        if name == 'Alaska':
            f = _xform_feature(feat, _ak_xform, {'code': 'AK'})
            lp = _label_pos(f['geometry'])
            f['properties']['label_lon'], f['properties']['label_lat'] = lp
            insets.append(f)
        elif name == 'Hawaii':
            f = _xform_feature(feat, _hi_xform, {'code': 'HI'})
            lp = _label_pos(f['geometry'])
            f['properties']['label_lon'], f['properties']['label_lat'] = lp
            insets.append(f)
    for feat in canada_data['features']:
        abbrev = CANADA_PROVINCE_MAP.get(feat['properties'].get('name', ''))
        if abbrev:
            # Strip small islands (Arctic clutter) before transforming
            feat = _strip_small_polygons(feat, min_bbox_area=0.5)
            f = _xform_feature(feat, _canada_xform, {'code': abbrev})
            lp = _label_pos(f['geometry'])
            f['properties']['label_lon'], f['properties']['label_lat'] = lp
            insets.append(f)
    return insets


def generate_state_animation_html(animation_data_file, boundaries_file, canada_boundaries_file,
                                   output_file, host_state, contest_name, title,
                                   about_text=STATE_ABOUT):
    with open(animation_data_file) as f:
        animation_data = json.load(f)
    with open(boundaries_file) as f:
        boundaries_data = json.load(f)
    with open(canada_boundaries_file) as f:
        canada_data = json.load(f)

    inset_features = _build_inset_features(boundaries_data, canada_data)
    contest_meta = {'contest_name': contest_name, 'host_state': host_state}

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {leaflet_head_html()}
    <style>
        body {{ margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ height: 100vh; width: 100%; background: white; }}
        {get_controls_css()}
        {get_legend_css()}
    </style>
</head>
<body>
    <div id="map"></div>
    {get_controls_html(about_text)}
    {get_legend_html()}
    <script>
        const animationData = {json.dumps(animation_data)};
        const boundariesData = {json.dumps(boundaries_data)};
        const insetData = {json.dumps({'type': 'FeatureCollection', 'features': inset_features})};
        const contestMeta = {json.dumps(contest_meta)};
        const hostState = '{host_state}';
        const stateMap = {json.dumps(US_STATE_MAP)};
        const excludedStates = {json.dumps(EXCLUDED_STATES)};
        const usStateCodes = new Set({json.dumps(list(US_STATE_CODES))});

        let map, stateLayer, insetLayer;

        {get_controls_js(str(ANIMATION_SPEEDS))}
        {get_legend_js(str(COLOR_THRESHOLDS), str(COLOR_PALETTE), "QSOs per State/Province")}

        map = L.map('map', {{ zoomDelta: 0.25, zoomSnap: 0.25 }});

        // ── Lower 48 ──────────────────────────────────────────────────────────
        const lower48 = boundariesData.features.filter(
            f => !excludedStates.includes(f.properties.name || ''));

        stateLayer = L.geoJSON({{ type: 'FeatureCollection', features: lower48 }}, {{
            style: f => getStateStyle(f),
            onEachFeature: (feature, layer) => {{
                layer.bindPopup(`<b>${{feature.properties.name}}</b><br>QSOs: 0`);
            }}
        }}).addTo(map);

        // ── Repositioned insets: AK, HI, Canadian provinces ──────────────────
        insetLayer = L.geoJSON(insetData, {{
            style: f => getInsetStyle(f),
            onEachFeature: (feature, layer) => {{
                const {{ code, name }} = feature.properties;
                layer.bindPopup(`<b>${{code}}</b><br>${{name || code}}<br>QSOs: 0`);
            }}
        }}).addTo(map);


        // Fit to lower 48 + insets combined
        const allBounds = L.geoJSON({{
            type: 'FeatureCollection',
            features: [...lower48, ...insetData.features]
        }}).getBounds();
        map.fitBounds(allBounds, {{ padding: [20, 20] }});

        // ── Styles ────────────────────────────────────────────────────────────
        function calcMaxQSOs(frame) {{
            const vals = Object.entries(frame.states || {{}})
                .filter(([s]) => s !== hostState).map(([, v]) => v);
            return vals.length > 0 ? Math.max(...vals) : 1;
        }}

        function getStateStyle(feature) {{
            const code = stateMap[feature.properties.name] || '';
            const frame = animationData.frames[currentFrame];
            const count = (frame && frame.states[code]) || 0;
            return {{ fillColor: getColor(count, calcMaxQSOs(frame)),
                      weight: 0.5, opacity: 0.8, color: '#666', fillOpacity: 0.75 }};
        }}

        function getInsetStyle(feature) {{
            const code = feature.properties.code || '';
            const frame = animationData.frames[currentFrame];
            const count = (frame && frame.states[code]) || 0;
            return {{ fillColor: getColor(count, calcMaxQSOs(frame)),
                      weight: 0.5, opacity: 0.8, color: '#666',
                      fillOpacity: 0.70 }};
        }}

        // ── Frame update ──────────────────────────────────────────────────────
        function updateFrame() {{
            const frame = animationData.frames[currentFrame];
            document.getElementById('dateDisplay').textContent = frame.date;
            document.getElementById('timeDisplay').textContent = frame.time + 'Z';
            document.getElementById('progressBar').style.width =
                ((currentFrame / (animationData.frames.length - 1)) * 100) + '%';

            const maxQSOs = calcMaxQSOs(frame);

            stateLayer.eachLayer(layer => {{
                const code = stateMap[layer.feature.properties.name] || '';
                const count = (frame.states && frame.states[code]) || 0;
                layer.setStyle({{ fillColor: getColor(count, maxQSOs) }});
                layer.getPopup().setContent(
                    `<b>${{layer.feature.properties.name}}</b><br>QSOs: ${{count}}`);
            }});

            insetLayer.eachLayer(layer => {{
                const code = layer.feature.properties.code || '';
                const count = (frame.states && frame.states[code]) || 0;
                layer.setStyle({{ fillColor: getColor(count, maxQSOs) }});
                layer.getPopup().setContent(
                    `<b>${{code}}</b><br>${{layer.feature.properties.name || code}}<br>QSOs: ${{count}}`);
            }});

            updateLegend(maxQSOs);

            const totalQsos = Object.values(frame.states || {{}}).reduce((s, v) => s + v, 0);
            const activeStates = Object.keys(frame.states || {{}})
                .filter(s => usStateCodes.has(s) && frame.states[s] > 0).length;
            document.getElementById('statusDisplay').textContent =
                `${{contestMeta.contest_name}} | QSOs: ${{totalQsos}} | Active States: ${{activeStates}}`;
        }}

        updateFrame();
    </script>
</body></html>'''

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        f.write(html)
    print(f"State animation saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate US state QSO animation')
    parser.add_argument('--animation-data', required=True)
    parser.add_argument('--boundaries', required=True,
                        help='Path to US states GeoJSON')
    parser.add_argument('--canada-boundaries', default='reference/canada_provinces.json',
                        help='Path to Canadian provinces GeoJSON')
    parser.add_argument('--output', required=True)
    parser.add_argument('--host-state', default='NY')
    parser.add_argument('--contest-name', required=True)
    parser.add_argument('--title', help='HTML page title')
    parser.add_argument('--about', default=STATE_ABOUT)
    args = parser.parse_args()

    generate_state_animation_html(
        args.animation_data, args.boundaries, args.canada_boundaries,
        args.output, args.host_state, args.contest_name,
        args.title or args.contest_name, args.about
    )


if __name__ == '__main__':
    main()
