#!/usr/bin/env python3
"""
Generate chart thumbnails and an HTML gallery page.
Discovers all PNG charts in the charts directory, creates thumbnails,
and builds a self-contained gallery HTML with relative paths.

Individual per-band charts are collapsed into a stitched composite
thumbnail on the landing page; clicking it opens a band sub-page
showing all six per-band charts plus the two all-bands summaries.
"""

import argparse
import os
from pathlib import Path
from PIL import Image

# Ordered list of per-band chart fragments (160m → 10m)
BAND_FRAGMENTS = [
    '160m_activity', '80m_activity', '40m_activity',
    '20m_activity',  '15m_activity', '10m_activity',
]
ALLBANDS_FRAGMENTS = ['allbands_cw', 'allbands_ph']

# Human-readable metadata keyed by filename fragment (case-insensitive match)
CHART_META = {
    'boxplotofscorebycat':        ('QSO Count by Category',
        'Distribution of QSO counts across contest categories (operator type, power, mode, station type).'),
    'distributionofqsos':         ('QSOs by Location & Mode',
        'Breakdown of QSO activity between NY and non-NY stations, split by CW and Phone modes.'),
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
    'wordcloud_composite_instate':  ('NY In-State Callsign Clouds',
        'Top NY callsigns by category (Mobile, Phone, Mixed, CW × power level) — click to explore.'),
    'wordcloud_composite_outstate': ('Out-of-State & DX Callsign Clouds',
        'Top out-of-state and DX callsigns by category — click to explore.'),
}

# Thumbnails that link to an HTML page instead of the full PNG.
# Key: filename fragment; Value: HTML filename suffix appended to contest prefix.
HTML_OVERRIDES = {
    'band_activity_composite':      '_band_activity.html',
    'wordcloud_composite_instate':  '_wordclouds_instate.html',
    'wordcloud_composite_outstate': '_wordclouds_outstate.html',
}


def _chart_meta(filename):
    """Return (title, description) for a chart filename."""
    lower = filename.lower()
    for key, meta in CHART_META.items():
        if key in lower:
            return meta
    stem = Path(filename).stem
    parts = stem.split('_', 1)
    title = parts[1].replace('_', ' ') if len(parts) > 1 else stem
    return title, ''


def _html_override(filename):
    """Return an HTML link target override for this chart, or None."""
    lower = filename.lower()
    for key, suffix in HTML_OVERRIDES.items():
        if key in lower:
            stem = Path(filename).stem
            idx = stem.lower().find(key.split('_')[0])
            contest_prefix = stem[:idx].rstrip('_')
            return contest_prefix.lower() + suffix
    return None


def _contest_prefix(charts_dir):
    """Derive the contest ID prefix from the first PNG found."""
    for png in sorted(charts_dir.glob('*.png')):
        lower = png.name.lower()
        for frag in BAND_FRAGMENTS + ALLBANDS_FRAGMENTS:
            if frag in lower:
                idx = lower.find(frag)
                return png.name[:idx].rstrip('_')
    return ''


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
    """Stitch the six per-band charts into a 2×3 composite.  Returns the Path or None."""
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
    w, h  = imgs[0].size
    cols  = 2
    rows  = (len(imgs) + cols - 1) // cols
    out   = Image.new('RGB', (cols * w, rows * h), (240, 240, 240))
    for i, img in enumerate(imgs):
        out.paste(img, ((i % cols) * w, (i // cols) * h))
    out.save(str(composite_path))
    print(f"  Band composite: {composite_path.name}")
    return composite_path


def _gallery_item(chart_path, charts_rel, thumbs_rel, link_override=None):
    title, desc = _chart_meta(chart_path.name)
    thumb_src = f"{thumbs_rel}/thumb_{chart_path.name}"
    override  = link_override if link_override is not None else _html_override(chart_path.name)
    full_src  = override if override else f"{charts_rel}/{chart_path.name}"
    return f'''
        <div class="chart-item">
            <img src="{thumb_src}" alt="{title}" class="chart-thumbnail"
                 onclick="window.open('{full_src}', '_blank')">
            <div class="chart-title">{title}</div>
            <div class="chart-description">{desc}</div>
        </div>'''


_GALLERY_CSS = '''
        body { font-family: Arial, sans-serif; margin: 0; padding: 1em; background: #f0f0f0; }
        h1   { text-align: center; color: #2c3e50; }
        p.sub { text-align: center; color: #666; font-size: 0.9em; margin-top: -0.5em; }
        a    { color: #1a6eb5; }
        .chart-gallery {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        .chart-item {
            background: #f9f9f9;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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


def generate_gallery_html(chart_files, charts_rel, thumbs_rel, contest_name):
    """Main landing page gallery HTML."""
    items_html = '\n'.join(
        _gallery_item(f, charts_rel, thumbs_rel) for f in chart_files
    )
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — Chart Gallery</title>
    <style>{_GALLERY_CSS}
    </style>
</head>
<body>
    <h1>{contest_name} — Analysis Charts</h1>
    <div class="chart-gallery">{items_html}
    </div>
</body>
</html>'''


def generate_band_subpage_html(charts_dir, subpage_path, thumbs_dir, gallery_html_path, contest_name):
    """Band activity sub-page: 6 per-band + 2 all-bands charts in a 2-column grid."""
    charts_rel = Path(os.path.relpath(charts_dir, subpage_path.parent))
    thumbs_rel = Path(os.path.relpath(thumbs_dir,  subpage_path.parent))
    gallery_rel = Path(os.path.relpath(gallery_html_path, subpage_path.parent))

    band_files = []
    for frag in BAND_FRAGMENTS + ALLBANDS_FRAGMENTS:
        matches = sorted(f for f in charts_dir.glob('*.png') if frag in f.name.lower())
        if matches:
            band_files.append(matches[0])

    items_html = '\n'.join(
        _gallery_item(f, charts_rel, thumbs_rel, link_override=f'{charts_rel}/{f.name}')
        for f in band_files
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — Band Activity</title>
    <style>{_GALLERY_CSS}
    </style>
</head>
<body>
    <h1>{contest_name} — Band Activity</h1>
    <p class="sub"><a href="{gallery_rel}">← Back to Chart Gallery</a></p>
    <div class="chart-gallery">{items_html}
    </div>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Generate chart thumbnails and gallery HTML')
    parser.add_argument('--charts-dir',   required=True, help='Directory containing PNG chart files')
    parser.add_argument('--output-html',  required=True, help='Output HTML file path')
    parser.add_argument('--contest-name', default='Contest', help='Contest display name')
    parser.add_argument('--thumb-width',  type=int, default=300)
    parser.add_argument('--thumb-height', type=int, default=200)
    args = parser.parse_args()

    charts_dir = Path(args.charts_dir)
    html_path  = Path(args.output_html)
    thumbs_dir = charts_dir / 'thumbnails'

    # Build band composite first so it gets thumbnailed in the same pass
    print("Building band composite...")
    band_composite = make_band_composite(charts_dir)

    print("Creating thumbnails...")
    all_files = create_thumbnails(charts_dir, thumbs_dir,
                                  thumb_size=(args.thumb_width, args.thumb_height))

    # Relative paths from the gallery HTML to charts/thumbnails
    charts_rel = Path(os.path.relpath(charts_dir, html_path.parent))
    thumbs_rel = Path(os.path.relpath(thumbs_dir,  html_path.parent))

    # Generate band sub-page
    if band_composite:
        prefix = _contest_prefix(charts_dir).lower()
        band_subpage = html_path.parent / f'{prefix}_band_activity.html'
        print("Generating band sub-page...")
        band_subpage.parent.mkdir(parents=True, exist_ok=True)
        with open(band_subpage, 'w') as f:
            f.write(generate_band_subpage_html(
                charts_dir, band_subpage, thumbs_dir, html_path, args.contest_name
            ))
        print(f"  Band sub-page saved to {band_subpage}")

    # Filter for landing page:
    #   - exclude individual per-band and all-bands charts (on sub-page)
    #   - exclude individual word cloud PNGs (composites handle them)
    def _is_band_chart(f):
        lower = f.name.lower()
        return any(frag in lower for frag in BAND_FRAGMENTS + ALLBANDS_FRAGMENTS)

    def _is_individual_wordcloud(f):
        lower = f.name.lower()
        return 'wordcloud' in lower and 'composite' not in lower

    chart_files = [
        f for f in all_files
        if not _is_band_chart(f) and not _is_individual_wordcloud(f)
    ]

    if not chart_files:
        print("No charts found — gallery not generated.")
        return

    print("Generating gallery HTML...")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(generate_gallery_html(chart_files, charts_rel, thumbs_rel, args.contest_name))
    print(f"Gallery saved to {html_path}")


if __name__ == '__main__':
    main()
