#!/usr/bin/env python3
"""
Generate callsign word clouds split by category, producing two HTML pages:
  - In-State: NY Mobile + 5 NY fixed/portable categories
  - Out-of-State: 5 OOS categories + DX

Each page shows 6 clouds in a 2x3 grid.  Composite PNG thumbnails are
also written to the charts directory for inclusion in the chart gallery.
"""

import argparse
import os
import sqlite3
from pathlib import Path

from PIL import Image
from wordcloud import WordCloud


MAX_WORDS = 15

# ---------------------------------------------------------------------------
# Cloud definitions: (key, title, location, station_type, mode, power, color)
#   location:     'NY' | 'DX' | None (= out-of-state, not NY and not DX)
#   station_type: 'MOBILE' | None (= any non-mobile)
#   mode/power:   DB values, or None = no filter
# ---------------------------------------------------------------------------
INSTATE_CLOUDS = [
    ('ny_mobile',   'NY Mobile Stations',      'NY',  'MOBILE', None,    None,   '#d73027'),
    ('ny_phone_lp', 'NY Phone — Low Power',    'NY',  None,     'SSB',   'LOW',  '#1a6eb5'),
    ('ny_mixed_lp', 'NY Mixed — Low Power',    'NY',  None,     'MIXED', 'LOW',  '#2ca25f'),
    ('ny_cw_lp',    'NY CW — Low Power',       'NY',  None,     'CW',    'LOW',  '#f46d43'),
    ('ny_mixed_hp', 'NY Mixed — High Power',   'NY',  None,     'MIXED', 'HIGH', '#74add1'),
    ('ny_phone_hp', 'NY Phone — High Power',   'NY',  None,     'SSB',   'HIGH', '#a50026'),
]

OUTSTATE_CLOUDS = [
    ('oos_cw_lp',    'Out-of-State CW — Low Power',    None, None, 'CW',    'LOW',  '#313695'),
    ('oos_phone_lp', 'Out-of-State Phone — Low Power', None, None, 'SSB',   'LOW',  '#d73027'),
    ('oos_mixed_lp', 'Out-of-State Mixed — Low Power', None, None, 'MIXED', 'LOW',  '#1a9850'),
    ('oos_cw_hp',    'Out-of-State CW — High Power',   None, None, 'CW',    'HIGH', '#4575b4'),
    ('oos_mixed_hp', 'Out-of-State Mixed — High Power',None, None, 'MIXED', 'HIGH', '#006837'),
    ('dx',           'DX Stations',                    'DX', None, None,    None,   '#8856a7'),
]

ALL_CLOUDS = INSTATE_CLOUDS + OUTSTATE_CLOUDS


def _single_color_fn(color):
    def fn(word, font_size, position, orientation, random_state=None, **kwargs):
        return color
    return fn


def fetch_all_frequency_maps(meta_db, qso_db):
    """Return {key: {callsign: weight}} for every cloud group."""
    meta_conn = sqlite3.connect(meta_db)
    stations = {}
    for r in meta_conn.execute(
        "SELECT callsign, location, station_type, mode, power, claimed_score, operator_category FROM stations"
    ).fetchall():
        stations[r[0]] = {
            'location': r[1], 'station_type': r[2],
            'mode': r[3], 'power': r[4], 'claimed_score': r[5],
            'operator_category': r[6],
        }
    meta_conn.close()

    qso_conn = sqlite3.connect(qso_db)
    counts = {r[0]: r[1] for r in qso_conn.execute(
        "SELECT station_call, COUNT(*) FROM valid_qsos GROUP BY station_call"
    ).fetchall()}
    qso_conn.close()

    maps = {defn[0]: {} for defn in ALL_CLOUDS}

    for call, n in counts.items():
        s = stations.get(call, {})
        loc   = s.get('location')
        stype = s.get('station_type')
        mode  = s.get('mode')
        power = s.get('power')
        score = s.get('claimed_score')
        op_cat = s.get('operator_category')

        for key, _title, f_loc, f_stype, f_mode, f_power, _color in ALL_CLOUDS:
            # Location filter
            if f_loc == 'NY'  and loc != 'NY':  continue
            if f_loc == 'DX'  and loc != 'DX':  continue
            if f_loc is None  and loc in ('NY', 'DX'):  continue
            # Station-type filter
            if f_stype == 'MOBILE' and stype != 'MOBILE': continue
            if f_stype is None and f_loc == 'NY' and stype == 'MOBILE': continue
            # All non-mobile clouds are single-op only; mobile cloud includes all op types
            if f_stype != 'MOBILE' and op_cat != 'SINGLE-OP': continue
            # Mode / power filters
            if f_mode  is not None and mode  != f_mode:  continue
            if f_power is not None and power != f_power: continue

            # Weight by claimed_score for everyone; fall back to QSO count if missing
            weight = score if score else n
            maps[key][call] = weight

    return maps


def make_wordcloud(freq, color, output_path, width=800, height=500):
    if not freq:
        print(f"  No data — skipping {output_path.name}")
        return False
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


def make_composite(cloud_pngs, output_path, cols=2):
    """Stitch word cloud PNGs into a cols-wide grid composite image."""
    imgs = [(p, t) for p, t in cloud_pngs if p.exists()]
    if not imgs:
        return False
    tiles = [Image.open(p) for p, _ in imgs]
    w, h  = tiles[0].size
    rows  = (len(tiles) + cols - 1) // cols
    composite = Image.new('RGB', (cols * w, rows * h), (240, 240, 240))
    for i, img in enumerate(tiles):
        composite.paste(img, ((i % cols) * w, (i // cols) * h))
    composite.save(str(output_path))
    print(f"  Saved composite: {output_path.name}")
    return True


def generate_html(clouds, html_path, contest_name, page_title, other_html=None, other_label=None):
    """Generate a 2x3 grid HTML page.

    clouds: list of (png_path, title) — only existing PNGs are shown.
    other_html / other_label: optional link to the companion page.
    """
    def img_tag(png_path, title):
        rel = Path(os.path.relpath(png_path, html_path.parent))
        return f'''
        <div class="cloud-item">
            <h2>{title}</h2>
            <img src="{rel}" alt="{title}" onclick="window.open('{rel}', '_blank')">
        </div>'''

    items = ''.join(img_tag(p, t) for p, t in clouds if p.exists())

    nav = ''
    if other_html and other_label:
        other_rel = Path(os.path.relpath(other_html, html_path.parent))
        nav = f'<p class="sub"><a href="{other_rel}">{other_label} →</a></p>'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{contest_name} — {page_title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 1em; background: #f0f0f0; }}
        h1 {{ text-align: center; color: #2c3e50; }}
        p.sub {{ text-align: center; color: #666; font-size: 0.9em; margin-top: -0.5em; }}
        a {{ color: #1a6eb5; }}
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
    <h1>{contest_name} — {page_title}</h1>
    <p class="sub">Top {MAX_WORDS} callsigns per group, sized by claimed score. Click any image to open full size.</p>
    {nav}
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
    parser.add_argument('--meta-db',            required=True)
    parser.add_argument('--qso-db',             required=True)
    parser.add_argument('--output-dir',         required=True, help='Directory for PNG files')
    parser.add_argument('--output-html-instate',  required=True, help='HTML path for NY in-state page')
    parser.add_argument('--output-html-outstate', required=True, help='HTML path for out-of-state/DX page')
    parser.add_argument('--contest-name',       default='Contest')
    parser.add_argument('--contest-id',         required=True)
    args = parser.parse_args()

    out_dir        = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    instate_html   = Path(args.output_html_instate)
    outstate_html  = Path(args.output_html_outstate)
    cid            = args.contest_id

    print("Fetching QSO counts...")
    maps = fetch_all_frequency_maps(args.meta_db, args.qso_db)
    for key, n in {k: len(v) for k, v in maps.items()}.items():
        print(f"  {key}: {n} stations")

    # Build PNG paths for each cloud group
    png_paths = {
        defn[0]: out_dir / f'{cid}_wordcloud_{defn[0]}.png'
        for defn in ALL_CLOUDS
    }

    print("Generating word clouds...")
    for key, title, _loc, _stype, _mode, _power, color in ALL_CLOUDS:
        make_wordcloud(maps[key], color, png_paths[key])

    instate_pairs  = [(png_paths[d[0]], d[1]) for d in INSTATE_CLOUDS]
    outstate_pairs = [(png_paths[d[0]], d[1]) for d in OUTSTATE_CLOUDS]

    print("Generating composites...")
    make_composite(instate_pairs,  out_dir / f'{cid}_wordcloud_composite_instate.png')
    make_composite(outstate_pairs, out_dir / f'{cid}_wordcloud_composite_outstate.png')

    print("Generating HTML pages...")
    generate_html(
        instate_pairs, instate_html, args.contest_name,
        'NY In-State Callsign Clouds',
        other_html=outstate_html, other_label='Out-of-State & DX Clouds',
    )
    generate_html(
        outstate_pairs, outstate_html, args.contest_name,
        'Out-of-State & DX Callsign Clouds',
        other_html=instate_html, other_label='NY In-State Clouds',
    )
    print("Done!")


if __name__ == '__main__':
    main()
