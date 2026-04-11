#!/usr/bin/env python3
"""
Generate three callsign word clouds (NY mobile, NY fixed, out-of-state)
and an HTML page displaying them together.
"""

import argparse
import os
import sqlite3
from pathlib import Path

from wordcloud import WordCloud
import matplotlib.pyplot as plt


# Color palettes per cloud
COLORS = {
    'mobile': '#d73027',   # red  — mobiles stand out
    'fixed':  '#1a6eb5',   # blue — NY fixed
    'out':    '#2ca25f',   # green — out of state
}


def _single_color_fn(color):
    """Return a wordcloud color_func that always uses the given hex color."""
    def fn(word, font_size, position, orientation, random_state=None, **kwargs):
        return color
    return fn


def fetch_frequency_maps(meta_db, qso_db):
    """Return three {callsign: qso_count} dicts."""
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

    ny_mobile, ny_fixed, out_of_state = {}, {}, {}
    for call, n in counts.items():
        loc, stype = stations.get(call, (None, None))
        if loc == 'NY':
            if stype == 'MOBILE':
                ny_mobile[call] = n
            else:
                ny_fixed[call] = n
        else:
            out_of_state[call] = n

    return ny_mobile, ny_fixed, out_of_state


def make_wordcloud(freq, color, output_path, width=800, height=500):
    if not freq:
        print(f"  No data — skipping {output_path.name}")
        return False
    wc = WordCloud(
        width=width, height=height,
        background_color='white',
        color_func=_single_color_fn(color),
        prefer_horizontal=0.85,
        min_font_size=10,
        max_words=200,
    ).generate_from_frequencies(freq)
    wc.to_file(str(output_path))
    print(f"  Saved {output_path.name}")
    return True


def generate_html(mobile_png, fixed_png, out_png, html_path, contest_name, charts_rel):
    def img_tag(png_path, title):
        rel = Path(os.path.relpath(png_path, html_path.parent))
        return f'''
        <div class="cloud-item">
            <h2>{title}</h2>
            <img src="{rel}" alt="{title}" onclick="window.open('{rel}', '_blank')">
        </div>'''

    items = ''
    if mobile_png.exists():
        items += img_tag(mobile_png, 'NY Mobile Stations')
    if fixed_png.exists():
        items += img_tag(fixed_png, 'NY Fixed Stations')
    if out_png.exists():
        items += img_tag(out_png, 'Out-of-State Stations')

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
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
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
    <p class="sub">Callsign size reflects total QSOs logged. Click any image to open full size.</p>
    <div class="cloud-grid">{items}
    </div>
</body>
</html>'''

    html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(html_path, 'w') as f:
        f.write(html)
    print(f"  Gallery saved to {html_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate callsign word clouds')
    parser.add_argument('--meta-db',      required=True)
    parser.add_argument('--qso-db',       required=True)
    parser.add_argument('--output-dir',   required=True, help='Directory for PNG files')
    parser.add_argument('--output-html',  required=True, help='Output HTML file path')
    parser.add_argument('--contest-name', default='Contest')
    parser.add_argument('--contest-id',   required=True)
    args = parser.parse_args()

    out_dir  = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = Path(args.output_html)
    cid = args.contest_id

    print("Fetching QSO counts...")
    ny_mobile, ny_fixed, out_of_state = fetch_frequency_maps(args.meta_db, args.qso_db)
    print(f"  NY mobile: {len(ny_mobile)} stations, NY fixed: {len(ny_fixed)}, Out-of-state: {len(out_of_state)}")

    mobile_png = out_dir / f'{cid}_wordcloud_ny_mobile.png'
    fixed_png  = out_dir / f'{cid}_wordcloud_ny_fixed.png'
    out_png    = out_dir / f'{cid}_wordcloud_out_of_state.png'

    print("Generating word clouds...")
    make_wordcloud(ny_mobile,    COLORS['mobile'], mobile_png)
    make_wordcloud(ny_fixed,     COLORS['fixed'],  fixed_png)
    make_wordcloud(out_of_state, COLORS['out'],    out_png)

    print("Generating HTML...")
    generate_html(mobile_png, fixed_png, out_png, html_path, args.contest_name,
                  out_dir.relative_to(html_path.parent) if False else out_dir)
    print("Done!")


if __name__ == '__main__':
    main()
