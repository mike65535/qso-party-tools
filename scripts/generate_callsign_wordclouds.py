#!/usr/bin/env python3
"""
Generate four callsign word clouds (NY mobile, NY fixed, out-of-state, DX)
and an HTML page displaying them in a 2x2 grid.
"""

import argparse
import os
import sqlite3
from pathlib import Path

from PIL import Image
from wordcloud import WordCloud


MAX_WORDS = 15

COLORS = {
    'mobile': '#d73027',   # red   — NY mobiles
    'fixed':  '#1a6eb5',   # blue  — NY fixed
    'out':    '#2ca25f',   # green — out of state
    'dx':     '#8856a7',   # purple — DX
}


def _single_color_fn(color):
    def fn(word, font_size, position, orientation, random_state=None, **kwargs):
        return color
    return fn


def fetch_frequency_maps(meta_db, qso_db):
    """Return four {callsign: qso_count} dicts: NY mobile, NY fixed, out-of-state, DX."""
    meta_conn = sqlite3.connect(meta_db)
    stations = {r[0]: (r[1], r[2]) for r in meta_conn.execute(
        "SELECT callsign, location, station_type FROM stations"
    ).fetchall()}
    meta_conn.close()

    qso_conn = sqlite3.connect(qso_db)
    counts = {r[0]: r[1] for r in qso_conn.execute(
        "SELECT station_call, COUNT(*) FROM valid_qsos GROUP BY station_call"
    ).fetchall()}
    qso_conn.close()

    ny_mobile, ny_fixed, out_of_state, dx = {}, {}, {}, {}
    for call, n in counts.items():
        loc, stype = stations.get(call, (None, None))
        if loc == 'NY':
            if stype == 'MOBILE':
                ny_mobile[call] = n
            else:
                ny_fixed[call] = n
        elif loc == 'DX':
            dx[call] = n
        else:
            out_of_state[call] = n

    return ny_mobile, ny_fixed, out_of_state, dx


def make_wordcloud(freq, color, output_path, width=800, height=500):
    if not freq:
        print(f"  No data — skipping {output_path.name}")
        return False
    # Keep only top MAX_WORDS by frequency
    top = dict(sorted(freq.items(), key=lambda x: x[1], reverse=True)[:MAX_WORDS])
    wc = WordCloud(
        width=width, height=height,
        background_color='white',
        color_func=_single_color_fn(color),
        prefer_horizontal=0.85,
        min_font_size=12,
        max_words=MAX_WORDS,
    ).generate_from_frequencies(top)
    wc.to_file(str(output_path))
    print(f"  Saved {output_path.name} ({len(top)} callsigns)")
    return True


def make_composite(cloud_pngs, output_path):
    """Stitch up to 4 word cloud PNGs into a 2x2 composite image."""
    imgs = [(p, t) for p, t in cloud_pngs if p.exists()]
    if not imgs:
        return False
    tiles = [Image.open(p) for p, _ in imgs]
    w, h = tiles[0].size
    cols, rows = 2, (len(tiles) + 1) // 2
    composite = Image.new('RGB', (cols * w, rows * h), (240, 240, 240))
    for i, img in enumerate(tiles):
        composite.paste(img, ((i % cols) * w, (i // cols) * h))
    composite.save(str(output_path))
    print(f"  Saved composite: {output_path.name}")
    return True


def generate_html(clouds, html_path, contest_name):
    """clouds: list of (png_path, title) tuples."""
    def img_tag(png_path, title):
        rel = Path(os.path.relpath(png_path, html_path.parent))
        return f'''
        <div class="cloud-item">
            <h2>{title}</h2>
            <img src="{rel}" alt="{title}" onclick="window.open('{rel}', '_blank')">
        </div>'''

    items = ''.join(img_tag(p, t) for p, t in clouds if p.exists())

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — Callsign Word Clouds</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 1em; background: #f0f0f0; }}
        h1 {{ text-align: center; color: #2c3e50; }}
        p.sub {{ text-align: center; color: #666; font-size: 0.9em; margin-top: -0.5em; }}
        .cloud-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            max-width: 1400px;
            margin: 1.5em auto;
            padding: 0 1em;
        }}
        .cloud-item {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.12);
            text-align: center;
        }}
        .cloud-item h2 {{
            font-size: 1.1em;
            color: #2c3e50;
            margin: 0 0 10px;
        }}
        .cloud-item img {{
            width: 100%;
            height: auto;
            border-radius: 4px;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .cloud-item img:hover {{ opacity: 0.85; }}
        @media (max-width: 700px) {{
            .cloud-grid {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <h1>{contest_name} — Callsign Word Clouds</h1>
    <p class="sub">Top {MAX_WORDS} callsigns per group, sized by QSO count. Click any image to open full size.</p>
    <div class="cloud-grid">{items}
    </div>
</body>
</html>'''

    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(html)
    print(f"  HTML saved to {html_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate callsign word clouds')
    parser.add_argument('--meta-db',      required=True)
    parser.add_argument('--qso-db',       required=True)
    parser.add_argument('--output-dir',   required=True, help='Directory for PNG files')
    parser.add_argument('--output-html',  required=True, help='Output HTML file path')
    parser.add_argument('--contest-name', default='Contest')
    parser.add_argument('--contest-id',   required=True)
    args = parser.parse_args()

    out_dir   = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = Path(args.output_html)
    cid       = args.contest_id

    print("Fetching QSO counts...")
    ny_mobile, ny_fixed, out_of_state, dx = fetch_frequency_maps(args.meta_db, args.qso_db)
    print(f"  NY mobile: {len(ny_mobile)}, NY fixed: {len(ny_fixed)}, "
          f"Out-of-state: {len(out_of_state)}, DX: {len(dx)}")

    mobile_png    = out_dir / f'{cid}_wordcloud_ny_mobile.png'
    fixed_png     = out_dir / f'{cid}_wordcloud_ny_fixed.png'
    out_png       = out_dir / f'{cid}_wordcloud_out_of_state.png'
    dx_png        = out_dir / f'{cid}_wordcloud_dx.png'
    composite_png = out_dir / f'{cid}_wordcloud_composite.png'

    clouds = [
        (mobile_png, 'NY Mobile Stations'),
        (fixed_png,  'NY Fixed Stations'),
        (out_png,    'Out-of-State Stations'),
        (dx_png,     'DX Stations'),
    ]

    print("Generating word clouds...")
    make_wordcloud(ny_mobile,    COLORS['mobile'], mobile_png)
    make_wordcloud(ny_fixed,     COLORS['fixed'],  fixed_png)
    make_wordcloud(out_of_state, COLORS['out'],    out_png)
    make_wordcloud(dx,           COLORS['dx'],     dx_png)

    print("Generating composite...")
    make_composite(clouds, composite_png)

    print("Generating HTML...")
    generate_html(clouds, html_path, args.contest_name)
    print("Done!")


if __name__ == '__main__':
    main()
