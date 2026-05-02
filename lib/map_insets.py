"""
Helpers for coordinate-transformed map insets (same approach as AK/HI in state animation).

Each inset is defined as:
  { "label": "...", "bounds": [[lon_min,lat_min],[lon_max,lat_max]],
                    "target": [[lon_min,lat_min],[lon_max,lat_max]] }

Features whose *largest polygon component's* bbox-center falls within 'bounds' are
stripped of tiny sub-polygons, then coordinate-transformed to 'target'.
The result is rendered as a layer on the main Leaflet map so it pans/zooms naturally.
"""

import copy
import json


def _largest_bbox_center(feature):
    """[lon, lat] of the bbox-center of the feature's largest polygon component.
    Using the largest polygon (not centroid) is reliable for MultiPolygons with
    many small islands far from the main landmass."""
    geom = feature['geometry']

    def ba(ring):
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    def bc(ring):
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

    if geom['type'] == 'Polygon':
        cx, cy = bc(geom['coordinates'][0])
        return [cx, cy]
    elif geom['type'] == 'MultiPolygon':
        best = max(geom['coordinates'], key=lambda p: ba(p[0]))
        cx, cy = bc(best[0])
        return [cx, cy]
    return None


def _strip_small_polys(feature, min_area=0.005):
    """Remove small polygon components (reduces island clutter in display)."""
    geom = feature['geometry']
    if geom['type'] != 'MultiPolygon':
        return feature

    def ba(poly):
        ring = poly[0]
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))

    kept = [p for p in geom['coordinates'] if ba(p) >= min_area]
    if not kept:
        kept = [max(geom['coordinates'], key=ba)]   # always keep at least one

    f = copy.deepcopy(feature)
    if len(kept) == 1:
        f['geometry'] = {'type': 'Polygon', 'coordinates': kept[0]}
    else:
        f['geometry'] = {'type': 'MultiPolygon', 'coordinates': kept}
    return f


def _xform_feature(feature, src, dst):
    """Linearly remap coordinates from src bbox to dst bbox."""
    def tx(p):
        px = (p[0] - src[0][0]) / (src[1][0] - src[0][0])
        py = (p[1] - src[0][1]) / (src[1][1] - src[0][1])
        return [dst[0][0] + px * (dst[1][0] - dst[0][0]),
                dst[0][1] + py * (dst[1][1] - dst[0][1])] + list(p[2:])

    def xr(ring): return [tx(p) for p in ring]
    def xp(poly): return [xr(r) for r in poly]

    f = copy.deepcopy(feature)
    g = f['geometry']
    if g['type'] == 'Polygon':
        g['coordinates'] = xp(g['coordinates'])
    elif g['type'] == 'MultiPolygon':
        g['coordinates'] = [xp(p) for p in g['coordinates']]
    return f


def build_inset_features(boundaries_data, insets, min_area=0.005):
    """
    Build a GeoJSON FeatureCollection of coordinate-transformed inset features.
    Each feature's largest-polygon bbox-center must fall within the inset's 'bounds'.
    """
    all_feats = []
    for inset in insets:
        if 'target' not in inset:
            continue
        src, dst = inset['bounds'], inset['target']
        for feat in boundaries_data.get('features', []):
            c = _largest_bbox_center(feat)
            if c is None:
                continue
            if src[0][0] <= c[0] <= src[1][0] and src[0][1] <= c[1] <= src[1][1]:
                f = _strip_small_polys(feat, min_area=min_area)
                f = _xform_feature(f, src, dst)
                all_feats.append(f)
    return {'type': 'FeatureCollection', 'features': all_feats}


def inset_frame_js(insets):
    """
    JS snippet to draw a labeled border rectangle around each inset's target area.
    Requires the main Leaflet map variable named 'map'.
    Requires CSS for .inset-map-label (see inset_label_css()).
    """
    if not insets:
        return ''
    lines = []
    for inset in insets:
        if 'target' not in inset:
            continue
        t = inset['target']
        lb = f'[[{t[0][1]},{t[0][0]}],[{t[1][1]},{t[1][0]}]]'
        label = json.dumps(inset['label'])
        lines.append(
            f"        L.rectangle({lb}, {{weight:2,color:'#2c3e50',fill:false,interactive:false}})\n"
            f"         .bindTooltip({label}, {{permanent:true,direction:'top',className:'inset-map-label',offset:[0,-4]}})\n"
            f"         .addTo(map);"
        )
    return '\n'.join(lines)


def inset_label_css():
    """CSS for the permanent tooltip labels on inset border frames."""
    return '''
        .inset-map-label.leaflet-tooltip {
            background: #2c3e50; border: none; border-radius: 3px; box-shadow: none;
            color: #ecf0f1; font-size: 11px; font-weight: bold; padding: 2px 8px; white-space: nowrap;
        }
        .inset-map-label.leaflet-tooltip::before { display: none; }'''
