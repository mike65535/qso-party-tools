#!/usr/bin/env python3
"""
Generate chart thumbnails and a self-contained HTML gallery page.
All images are embedded as base64 data URIs — no external file dependencies.
A lightbox handles full-size chart viewing in-page.

Individual per-band charts are collapsed into a stitched composite
thumbnail; clicking it opens a band sub-page with all band charts.
"""

import argparse
import base64
import os
from pathlib import Path
from PIL import Image

# Ordered list of per-band chart fragments (160m → 10m)
BAND_FRAGMENTS = [
    '160m_activity', '80m_activity', '40m_activity',
    '20m_activity',  '15m_activity', '10m_activity',
]
ALLBANDS_FRAGMENTS = ['allbands_cw', 'allbands_ph']

def _build_chart_meta(host_type='State'):
    ht  = host_type
    htl = host_type.lower()
    return {
        'boxplotofscorebycat':        ('QSO Count by Category',
            'Distribution of QSO counts across contest categories (operator type, power, mode, station type).'),
        'distributionofqsos':         ('QSOs by Location & Mode',
            f'Breakdown of QSO activity between in-{htl} and out-of-{htl} stations, split by CW and Phone modes.'),
        'histogramofqso':             ('QSO Totals Distribution',
            'How many stations achieved different QSO count levels during the contest.'),
        'band_activity_composite':    ('Band Activity — All Bands',
            'Per-band QSO activity over the contest period (160m–10m) — click to explore all bands.'),
        '160m_activity':              ('160m Band Activity',
            'QSO activity over time on 160 meters, CW and Phone.'),
        '80m_activity':               ('80m Band Activity',
            'QSO activity over time on 80 meters, CW and Phone.'),
        '40m_activity':               ('40m Band Activity',
            'QSO activity over time on 40 meters, CW and Phone.'),
        '20m_activity':               ('20m Band Activity',
            'QSO activity over time on 20 meters, CW and Phone.'),
        '15m_activity':               ('15m Band Activity',
            'QSO activity over time on 15 meters, CW and Phone.'),
        '10m_activity':               ('10m Band Activity',
            'QSO activity over time on 10 meters, CW and Phone.'),
        'allbands_cw':                ('All Bands — CW Mode',
            'Stacked view of CW activity across all HF bands (160m–10m) over the contest period.'),
        'allbands_ph':                ('All Bands — Phone Mode',
            'Stacked view of Phone activity across all HF bands (160m–10m) over the contest period.'),
        'wordcloud_composite_instate':  (f'In-{ht} Callsign Clouds',
            f'Top in-{htl} callsigns by category (Mobile, Phone, Mixed, CW × power level) — click to explore.'),
        'wordcloud_composite_outstate': (f'Out-of-{ht} & DX Callsign Clouds',
            f'Top out-of-{htl} and DX callsigns by category — click to explore.'),
    }

# Thumbnails that link to a sibling HTML page instead of opening the full PNG.
# Key: filename fragment; Value: HTML filename suffix appended to contest prefix.
HTML_OVERRIDES = {
    'band_activity_composite':      '_band_activity.html',
    'wordcloud_composite_instate':  '_wordclouds_instate.html',
    'wordcloud_composite_outstate': '_wordclouds_outstate.html',
}

# ── Lightbox CSS + JS (shared by gallery and band sub-page) ─────────────────
_LIGHTBOX_CSS = '''
        #lightbox {
            display: none; position: fixed; inset: 0;
            background: rgba(0,0,0,0.88); z-index: 9999;
            align-items: center; justify-content: center; cursor: pointer;
        }
        #lightbox.open { display: flex; }
        #lb-img {
            max-width: 92vw; max-height: 92vh;
            border-radius: 6px; box-shadow: 0 8px 32px rgba(0,0,0,.6);
        }
        #lb-close {
            position: fixed; top: 14px; right: 22px;
            color: #fff; font-size: 30px; line-height: 1;
            cursor: pointer; user-select: none; opacity: 0.8;
        }
        #lb-close:hover { opacity: 1; }'''

_LIGHTBOX_HTML = '''
    <div id="lightbox" onclick="hideLB()">
        <span id="lb-close" onclick="hideLB()">&#x2715;</span>
        <img id="lb-img" src="" alt="" onclick="event.stopPropagation()">
    </div>'''

_LIGHTBOX_JS = '''
        function showLB(i) {
            document.getElementById('lb-img').src = CHARTS[i];
            document.getElementById('lightbox').classList.add('open');
        }
        function hideLB() {
            document.getElementById('lightbox').classList.remove('open');
            document.getElementById('lb-img').src = '';
        }
        document.addEventListener('keydown', e => { if (e.key === 'Escape') hideLB(); });'''

# ── Shared gallery CSS ───────────────────────────────────────────────────────
_GALLERY_CSS = '''
        body { font-family: Arial, sans-serif; margin: 0; padding: 1em; background: #f0f0f0; }
        h1   { text-align: center; color: #2c3e50; }
        p.sub { text-align: center; color: #666; font-size: 0.9em; margin-top: -0.5em; }
        a    { color: #1a6eb5; }
        .chart-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px; padding: 20px;
            max-width: 1200px; margin: 0 auto;
        }
        .chart-item {
            background: #f9f9f9; border-radius: 8px; padding: 15px;
            text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }
        .chart-item:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        .chart-thumbnail {
            width: 100%; height: auto; border-radius: 4px;
            cursor: pointer; transition: opacity 0.2s ease;
        }
        .chart-thumbnail:hover { opacity: 0.8; }
        .chart-title { font-size: 16px; font-weight: bold; margin: 10px 0 5px; color: #333; }
        .chart-description { font-size: 14px; color: #666; line-height: 1.4; }
        @media (max-width: 768px) {
            .chart-gallery { grid-template-columns: 1fr; padding: 10px; gap: 15px; }
            .chart-title { font-size: 14px; }
            .chart-description { font-size: 12px; }
        }'''


# ── Helpers ──────────────────────────────────────────────────────────────────

def _embed_image(path):
    """Return a base64 PNG data URI, or empty string on error."""
    try:
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{data}'
    except Exception:
        return ''


def _chart_meta(filename, chart_meta):
    lower = filename.lower()
    for key, meta in chart_meta.items():
        if key in lower:
            return meta
    stem = Path(filename).stem
    parts = stem.split('_', 1)
    return (parts[1].replace('_', ' ') if len(parts) > 1 else stem), ''


def _html_override(filename):
    """Return the sibling HTML filename for this chart, or None."""
    lower = filename.lower()
    for key, suffix in HTML_OVERRIDES.items():
        if key in lower:
            stem = Path(filename).stem
            idx  = stem.lower().find(key.split('_')[0])
            return stem[:idx].rstrip('_').lower() + suffix
    return None


def _contest_prefix(charts_dir):
    for png in sorted(charts_dir.glob('*.png')):
        lower = png.name.lower()
        for frag in BAND_FRAGMENTS + ALLBANDS_FRAGMENTS:
            if frag in lower:
                return png.name[:lower.find(frag)].rstrip('_')
    return ''


# ── Thumbnail creation + composite ──────────────────────────────────────────

def create_thumbnails(charts_dir, thumbs_dir, thumb_size=(300, 200)):
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for chart_path in sorted(charts_dir.glob('*.png')):
        thumb_path = thumbs_dir / f"thumb_{chart_path.name}"
        try:
            with Image.open(chart_path) as img:
                if img.mode in ('RGBA', 'LA'):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                img.save(thumb_path, 'PNG')
                print(f"  Thumbnail: {thumb_path.name}")
                created.append(chart_path)
        except Exception as e:
            print(f"  Error thumbnailing {chart_path.name}: {e}")
    return created


def make_band_composite(charts_dir):
    per_band = []
    for frag in BAND_FRAGMENTS:
        matches = sorted(f for f in charts_dir.glob('*.png') if frag in f.name.lower())
        if matches:
            per_band.append(matches[0])
    if not per_band:
        return None
    prefix = _contest_prefix(charts_dir)
    composite_path = charts_dir / f'{prefix}_band_activity_composite.png'
    imgs = [Image.open(p) for p in per_band]
    w, h = imgs[0].size
    cols, rows = 2, (len(imgs) + 1) // 2
    out = Image.new('RGB', (cols * w, rows * h), (240, 240, 240))
    for i, img in enumerate(imgs):
        out.paste(img, ((i % cols) * w, (i // cols) * h))
    out.save(str(composite_path))
    print(f"  Band composite: {composite_path.name}")
    return composite_path


# ── HTML generation ──────────────────────────────────────────────────────────

def _build_items(chart_files, thumbs_dir, chart_meta):
    """Return (items_html, charts_js_array_literal).

    PNG charts go into a CHARTS[] array for the lightbox.
    HTML-linked charts use window.open on the sibling HTML filename.
    """
    charts_b64  = []   # base64 strings for lightbox CHARTS array
    item_blocks = []

    for chart_path in chart_files:
        title, desc = _chart_meta(chart_path.name, chart_meta)
        thumb_path  = thumbs_dir / f"thumb_{chart_path.name}"
        thumb_b64   = _embed_image(thumb_path)
        html_target = _html_override(chart_path.name)

        if html_target:
            onclick = f"window.open('{html_target}','_blank')"
        else:
            idx = len(charts_b64)
            charts_b64.append(_embed_image(chart_path))
            onclick = f"showLB({idx})"

        item_blocks.append(f'''
        <div class="chart-item">
            <img src="{thumb_b64}" alt="{title}" class="chart-thumbnail"
                 onclick="{onclick}">
            <div class="chart-title">{title}</div>
            <div class="chart-description">{desc}</div>
        </div>''')

    # Build JS array literal
    joined = ',\n  '.join(f"'{b}'" for b in charts_b64)
    charts_js = f'const CHARTS = [\n  {joined}\n];' if charts_b64 else 'const CHARTS = [];'

    return '\n'.join(item_blocks), charts_js


def generate_gallery_html(chart_files, thumbs_dir, contest_name, host_type='State'):
    items_html, charts_js = _build_items(chart_files, thumbs_dir, _build_chart_meta(host_type))
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — Chart Gallery</title>
    <style>{_GALLERY_CSS}{_LIGHTBOX_CSS}
    </style>
</head>
<body>
    <h1>{contest_name} — Analysis Charts</h1>
    <div class="chart-gallery">{items_html}
    </div>
    {_LIGHTBOX_HTML}
    <script>
        {charts_js}
        {_LIGHTBOX_JS}
    </script>
</body>
</html>'''


def generate_band_subpage_html(charts_dir, thumbs_dir, gallery_html_name, contest_name,
                               host_type='State'):
    """Self-contained band sub-page; gallery_html_name is just the filename (same dir)."""
    chart_meta = _build_chart_meta(host_type)
    band_files = []
    for frag in BAND_FRAGMENTS + ALLBANDS_FRAGMENTS:
        matches = sorted(f for f in charts_dir.glob('*.png') if frag in f.name.lower())
        if matches:
            band_files.append(matches[0])

    charts_b64 = [_embed_image(p) for p in band_files]
    joined = ',\n  '.join(f"'{b}'" for b in charts_b64)
    charts_js = f'const CHARTS = [\n  {joined}\n];'

    items_html = ''
    for i, chart_path in enumerate(band_files):
        title, desc = _chart_meta(chart_path.name, chart_meta)
        thumb_b64   = _embed_image(thumbs_dir / f"thumb_{chart_path.name}")
        items_html += f'''
        <div class="chart-item">
            <img src="{thumb_b64}" alt="{title}" class="chart-thumbnail"
                 onclick="showLB({i})">
            <div class="chart-title">{title}</div>
            <div class="chart-description">{desc}</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — Band Activity</title>
    <style>{_GALLERY_CSS}{_LIGHTBOX_CSS}
    </style>
</head>
<body>
    <h1>{contest_name} — Band Activity</h1>
    <p class="sub"><a href="{gallery_html_name}">&#8592; Back to Chart Gallery</a></p>
    <div class="chart-gallery">{items_html}
    </div>
    {_LIGHTBOX_HTML}
    <script>
        {charts_js}
        {_LIGHTBOX_JS}
    </script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Generate self-contained chart gallery HTML')
    parser.add_argument('--charts-dir',   required=True)
    parser.add_argument('--output-html',  required=True)
    parser.add_argument('--contest-name', default='Contest')
    parser.add_argument('--host-type',    default='State', help='Term for the host jurisdiction (e.g. State, Province)')
    parser.add_argument('--thumb-width',  type=int, default=300)
    parser.add_argument('--thumb-height', type=int, default=200)
    args = parser.parse_args()

    charts_dir = Path(args.charts_dir)
    html_path  = Path(args.output_html)
    thumbs_dir = charts_dir / 'thumbnails'

    print("Building band composite...")
    band_composite = make_band_composite(charts_dir)

    print("Creating thumbnails...")
    all_files = create_thumbnails(charts_dir, thumbs_dir,
                                  thumb_size=(args.thumb_width, args.thumb_height))

    # Band sub-page
    if band_composite:
        prefix     = _contest_prefix(charts_dir).lower()
        band_subpage = html_path.parent / f'{prefix}_band_activity.html'
        print("Generating band sub-page...")
        band_subpage.parent.mkdir(parents=True, exist_ok=True)
        with open(band_subpage, 'w') as f:
            f.write(generate_band_subpage_html(
                charts_dir, thumbs_dir, html_path.name, args.contest_name,
                host_type=args.host_type,
            ))
        print(f"  Band sub-page: {band_subpage}")

    def _is_band_chart(f):
        lower = f.name.lower()
        return any(frag in lower for frag in BAND_FRAGMENTS + ALLBANDS_FRAGMENTS)

    def _is_individual_wordcloud(f):
        lower = f.name.lower()
        return 'wordcloud' in lower and 'composite' not in lower

    chart_files = [f for f in all_files
                   if not _is_band_chart(f) and not _is_individual_wordcloud(f)]

    if not chart_files:
        print("No charts found — gallery not generated.")
        return

    print("Generating gallery HTML...")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(generate_gallery_html(chart_files, thumbs_dir, args.contest_name, args.host_type))
    print(f"Gallery saved to {html_path}")


if __name__ == '__main__':
    main()
