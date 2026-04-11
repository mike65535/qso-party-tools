#!/usr/bin/env python3
"""
Generate chart thumbnails and an HTML gallery page.
Discovers all PNG charts in the charts directory, creates thumbnails,
and builds a self-contained gallery HTML with relative paths.
"""

import argparse
import os
from pathlib import Path
from PIL import Image

# Human-readable metadata keyed by filename fragment (case-insensitive match)
CHART_META = {
    'boxplotofscorebycat': ('QSO Count by Category',
        'Distribution of QSO counts across contest categories (operator type, power, mode, station type).'),
    'distributionofqsos':  ('QSOs by Location & Mode',
        'Breakdown of QSO activity between NY and non-NY stations, split by CW and Phone modes.'),
    'histogramofqso':      ('QSO Totals Distribution',
        'How many stations achieved different QSO count levels during the contest.'),
    '160m_activity':       ('160m Band Activity',
        'QSO activity over time on 160 meters, CW and Phone.'),
    '80m_activity':        ('80m Band Activity',
        'QSO activity over time on 80 meters, CW and Phone.'),
    '40m_activity':        ('40m Band Activity',
        'QSO activity over time on 40 meters, CW and Phone.'),
    '20m_activity':        ('20m Band Activity',
        'QSO activity over time on 20 meters, CW and Phone.'),
    '15m_activity':        ('15m Band Activity',
        'QSO activity over time on 15 meters, CW and Phone.'),
    '10m_activity':        ('10m Band Activity',
        'QSO activity over time on 10 meters, CW and Phone.'),
    'allbands_cw':         ('All Bands — CW Mode',
        'Stacked view of CW activity across all HF bands (160m–10m) over the contest period.'),
    'allbands_ph':         ('All Bands — Phone Mode',
        'Stacked view of Phone activity across all HF bands (160m–10m) over the contest period.'),
}

def _chart_meta(filename):
    """Return (title, description) for a chart filename."""
    lower = filename.lower()
    for key, meta in CHART_META.items():
        if key in lower:
            return meta
    # Fallback: humanize the filename
    stem = Path(filename).stem
    parts = stem.split('_', 1)
    title = parts[1].replace('_', ' ') if len(parts) > 1 else stem
    return title, ''


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


def generate_gallery_html(chart_files, charts_rel, thumbs_rel, contest_name):
    """Return full gallery HTML. Paths are relative to the output HTML file."""
    items = []
    for chart_path in chart_files:
        title, desc = _chart_meta(chart_path.name)
        thumb_src = f"{thumbs_rel}/thumb_{chart_path.name}"
        full_src  = f"{charts_rel}/{chart_path.name}"
        items.append(f'''
        <div class="chart-item">
            <img src="{thumb_src}" alt="{title}" class="chart-thumbnail"
                 onclick="window.open('{full_src}', '_blank')">
            <div class="chart-title">{title}</div>
            <div class="chart-description">{desc}</div>
        </div>''')

    items_html = '\n'.join(items)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — Chart Gallery</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 1em; background: #f0f0f0; }}
        h1 {{ text-align: center; color: #2c3e50; }}
        .chart-gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .chart-item {{
            background: #f9f9f9;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s ease;
        }}
        .chart-item:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }}
        .chart-thumbnail {{
            width: 100%; height: auto; border-radius: 4px;
            cursor: pointer; transition: opacity 0.2s ease;
        }}
        .chart-thumbnail:hover {{ opacity: 0.8; }}
        .chart-title {{ font-size: 16px; font-weight: bold; margin: 10px 0 5px; color: #333; }}
        .chart-description {{ font-size: 14px; color: #666; line-height: 1.4; }}
        @media (max-width: 768px) {{
            .chart-gallery {{ grid-template-columns: 1fr; padding: 10px; gap: 15px; }}
            .chart-title {{ font-size: 14px; }}
            .chart-description {{ font-size: 12px; }}
        }}
    </style>
</head>
<body>
    <h1>{contest_name} — Analysis Charts</h1>
    <div class="chart-gallery">{items_html}
    </div>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Generate chart thumbnails and gallery HTML')
    parser.add_argument('--charts-dir', required=True, help='Directory containing PNG chart files')
    parser.add_argument('--output-html', required=True, help='Output HTML file path')
    parser.add_argument('--contest-name', default='Contest', help='Contest display name')
    parser.add_argument('--thumb-width',  type=int, default=300)
    parser.add_argument('--thumb-height', type=int, default=200)
    args = parser.parse_args()

    charts_dir = Path(args.charts_dir)
    html_path  = Path(args.output_html)
    thumbs_dir = charts_dir / 'thumbnails'

    print("Creating thumbnails...")
    chart_files = create_thumbnails(charts_dir, thumbs_dir,
                                    thumb_size=(args.thumb_width, args.thumb_height))
    if not chart_files:
        print("No charts found — gallery not generated.")
        return

    # Compute relative paths from the HTML file to the charts/thumbnails dirs
    charts_rel = Path(os.path.relpath(charts_dir, html_path.parent))
    thumbs_rel = Path(os.path.relpath(thumbs_dir, html_path.parent))

    print("Generating gallery HTML...")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(generate_gallery_html(chart_files, charts_rel, thumbs_rel, args.contest_name))
    print(f"Gallery saved to {html_path}")


if __name__ == '__main__':
    main()
