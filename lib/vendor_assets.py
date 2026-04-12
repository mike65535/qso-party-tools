"""
Inline vendor asset loader.
Returns Leaflet and Turf source as strings for embedding in self-contained HTML.
"""

from pathlib import Path

_VENDOR_DIR = Path(__file__).parent / 'vendor'


def _read(filename):
    return (_VENDOR_DIR / filename).read_text(encoding='utf-8')


def leaflet_css():
    return _read('leaflet.css')

def leaflet_js():
    return _read('leaflet.js')

def turf_js():
    return _read('turf.min.js')


def leaflet_head_html():
    """Drop-in replacement for the two CDN <link>/<script> tags — Leaflet only."""
    return f'<style>\n{leaflet_css()}\n</style>\n    <script>\n{leaflet_js()}\n</script>'


def leaflet_turf_head_html():
    """Drop-in replacement for the three CDN tags — Leaflet + Turf."""
    return (f'<style>\n{leaflet_css()}\n</style>\n'
            f'    <script>\n{leaflet_js()}\n</script>\n'
            f'    <script>\n{turf_js()}\n</script>')
