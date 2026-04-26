#!/usr/bin/env python3
"""
Generate the contest analysis landing page.
One page linking to every visualization and data output.

Two card types:
  tool-card   — interactive HTML tools (animations, maps); colored banner header
  chart-card  — chart/cloud pages with a real thumbnail image
"""

import argparse
import base64
import os
import sqlite3
from pathlib import Path


def _embed_image(path):
    """Return a base64 PNG data URI, or empty string on error."""
    try:
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('ascii')
        return f'data:image/png;base64,{data}'
    except Exception:
        return ''


def _has_mobiles(mobiles_json):
    """Return True if any mobile stations appear in the mobiles JSON."""
    if not mobiles_json:
        return True   # unknown — assume yes so card description stays positive
    try:
        import json as _json
        with open(mobiles_json, 'r') as f:
            return bool(_json.load(f))
    except Exception:
        return True


def _build_tool_cards(host_state, region_term, host_type='State', mobiles_json=None):
    rt = region_term.lower()
    if _has_mobiles(mobiles_json):
        mobile_desc = (f'Follow each mobile station across the map as it activates {rt}s '
                       f'throughout the contest period.')
    else:
        mobile_desc = f'No in-{host_type} mobile stations were active during this contest.'
    return [
        (f'{region_term} Activity Animation',
         f'Watch QSO activity build across {host_state} {rt}s hour by hour '
         f'as the contest unfolds.',
         '_county_animation.html',
         '#2c7bb6'),
        ('Mobile Station Activity',
         mobile_desc,
         '_mobile_animation.html',
         '#c0392b'),
        ('US and Canada Activity',
         'See how participation from every state and Canadian province '
         'grew over the contest period.',
         '_state_animation.html',
         '#1a9850'),
        (f'{host_state} {region_term} Map',
         f'Choropleth map of total QSO counts by {host_state} {rt} for all '
         f'log-submitting stations.',
         '_enhanced_map.html',
         '#6c3483'),
    ]


def _build_chart_cards(host_state, host_type='State'):
    ht = host_type.lower()
    return [
        ('Analysis Charts',
         'Statistical breakdowns by category, band activity over time, '
         'QSO distributions, and more.',
         '_chart_gallery.html',
         'BoxPlotOfScoreByCategory'),
        (f'{host_state} In-{host_type} Callsign Clouds',
         f'Top {host_state} callsigns by category — Mobile, Phone, Mixed, and CW '
         f'at each power level — sized by claimed score.',
         '_wordclouds_instate.html',
         'wordcloud_composite_instate'),
        (f'Out-of-{host_type} & DX Callsign Clouds',
         f'Top out-of-{ht} and DX callsigns by mode and power, '
         f'sized by claimed score.',
         '_wordclouds_outstate.html',
         'wordcloud_composite_outstate'),
    ]


STATS_CARD = (
    'Contest Statistics',
    'Detailed entry counts, score summaries, multiplier breakdowns, '
    'and top performers by category.',
    '_contest_stats.html',
    '#2c3e50',
)


def _find_thumb_b64(thumbs_dir, fragment):
    """Return base64 data URI for first thumbnail matching fragment, or empty string."""
    for p in sorted(thumbs_dir.glob('thumb_*.png')):
        if fragment.lower() in p.name.lower():
            return _embed_image(p)
    return ''


def _rel(from_html, to_path):
    return Path(os.path.relpath(to_path, from_html.parent))


def _pull_stats(meta_db, qso_db):
    """Return (logs, qsos) from the databases."""
    try:
        logs = sqlite3.connect(meta_db).execute(
            "SELECT COUNT(*) FROM stations WHERE operator_category != 'CHECKLOG'"
        ).fetchone()[0]
        qsos = sqlite3.connect(qso_db).execute(
            "SELECT COUNT(*) FROM valid_qsos"
        ).fetchone()[0]
        return logs, qsos
    except Exception:
        return None, None


def generate_landing_html(contest_name, contest_id, html_dir, thumbs_dir,
                          output_html, meta_db=None, qso_db=None, dx_countries=None,
                          host_state='NY', host_type='State', region_term='County',
                          mobiles_json=None):

    cid = contest_id.lower()
    stats = _pull_stats(meta_db, qso_db) if (meta_db and qso_db) else (None, None)
    logs, qsos = stats

    tool_cards  = _build_tool_cards(host_state, region_term, host_type, mobiles_json)
    chart_cards = _build_chart_cards(host_state, host_type)

    # ---- header stats badges ----
    badge_html = ''
    if logs:
        badge_html += f'<span class="badge">{logs:,} Logs</span>'
    if qsos:
        badge_html += f'<span class="badge">{qsos:,} QSOs Checked</span>'
    if dx_countries:
        badge_html += f'<span class="badge">{dx_countries} DX Countries</span>'

    # ---- tool cards ----
    tool_items = []
    for title, desc, suffix, color in tool_cards:
        target = html_dir / f'{cid}{suffix}'
        if not target.exists():
            continue
        href = target.name   # sibling file
        tool_items.append(f'''
      <a class="card tool-card" href="{href}">
        <div class="tool-banner" style="background:{color}">
          <div class="tool-title">{title}</div>
        </div>
        <div class="card-body">
          <p class="card-desc">{desc}</p>
          <span class="card-link">Open &rarr;</span>
        </div>
      </a>''')

    # ---- chart / cloud cards ----
    chart_items = []
    for title, desc, suffix, thumb_frag in chart_cards:
        target = html_dir / f'{cid}{suffix}'
        if not target.exists():
            continue
        href      = target.name   # sibling file — just the filename
        thumb_b64 = _find_thumb_b64(thumbs_dir, thumb_frag)
        thumb_tag = (f'<img class="card-thumb" src="{thumb_b64}" alt="{title}">'
                     if thumb_b64 else '<div class="thumb-placeholder"></div>')
        chart_items.append(f'''
      <a class="card chart-card" href="{href}">
        {thumb_tag}
        <div class="card-body">
          <div class="card-title">{title}</div>
          <p class="card-desc">{desc}</p>
          <span class="card-link">Open &rarr;</span>
        </div>
      </a>''')

    # ---- stats card ----
    stats_item = ''
    s_title, s_desc, s_suffix, s_color = STATS_CARD
    stats_target = html_dir / f'{cid}{s_suffix}'
    if stats_target.exists():
        href = stats_target.name   # sibling file
        stats_item = f'''
      <a class="card tool-card" href="{href}">
        <div class="tool-banner" style="background:{s_color}">
          <div class="tool-title">{s_title}</div>
        </div>
        <div class="card-body">
          <p class="card-desc">{s_desc}</p>
          <span class="card-link">Open &rarr;</span>
        </div>
      </a>'''

    tool_section = f'''
    <h2 class="section-title">Interactive Tools</h2>
    <div class="card-grid">{''.join(tool_items)}
    </div>''' if tool_items else ''

    chart_section = f'''
    <h2 class="section-title">Analysis Charts &amp; Callsign Clouds</h2>
    <div class="card-grid">{''.join(chart_items)}
    </div>''' if chart_items else ''

    stats_section = f'''
    <h2 class="section-title">Contest Data</h2>
    <div class="card-grid">{stats_item}
    </div>''' if stats_item else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{contest_name} — Analysis &amp; Visualizations</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: Arial, sans-serif;
      margin: 0; padding: 0;
      background: #eef0f3;
      color: #222;
    }}

    /* ---- header ---- */
    .page-header {{
      background: #1a252f;
      color: white;
      text-align: center;
      padding: 2em 1em 1.6em;
    }}
    .page-header h1 {{
      margin: 0 0 0.2em;
      font-size: clamp(1.4em, 4vw, 2.2em);
      font-weight: bold;
      letter-spacing: 0.02em;
    }}
    .page-header .subtitle {{
      font-size: 1em;
      color: #aab4be;
      margin: 0 0 1em;
    }}
    .badges {{ display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }}
    .badge {{
      background: #2c3e50;
      border: 1px solid #3d5166;
      border-radius: 20px;
      padding: 4px 14px;
      font-size: 0.85em;
      color: #d0d8e0;
    }}

    /* ---- layout ---- */
    .page-content {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 1.5em 1.2em 3em;
    }}
    .section-title {{
      font-size: 1.1em;
      font-weight: bold;
      color: #2c3e50;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      border-left: 4px solid #2c7bb6;
      padding-left: 10px;
      margin: 2em 0 1em;
    }}
    .card-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 18px;
    }}

    /* ---- cards ---- */
    .card {{
      background: white;
      border-radius: 10px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.10);
      overflow: hidden;
      text-decoration: none;
      color: inherit;
      display: flex;
      flex-direction: column;
      transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .card:hover {{
      transform: translateY(-3px);
      box-shadow: 0 6px 16px rgba(0,0,0,0.15);
    }}
    .tool-banner {{
      height: 110px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 1.2em;
    }}
    .tool-title {{
      color: white;
      font-size: 1.15em;
      font-weight: bold;
      text-align: center;
      line-height: 1.3;
      text-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
    .card-thumb {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .thumb-placeholder {{
      height: 110px;
      background: #dde;
    }}
    .card-body {{
      padding: 14px 16px 16px;
      display: flex;
      flex-direction: column;
      flex: 1;
    }}
    .card-title {{
      font-size: 1em;
      font-weight: bold;
      color: #2c3e50;
      margin: 0 0 6px;
    }}
    .card-desc {{
      font-size: 0.88em;
      color: #555;
      line-height: 1.5;
      margin: 0;
      flex: 1;
    }}
    .card-link {{
      display: inline-block;
      margin-top: 12px;
      font-size: 0.85em;
      font-weight: bold;
      color: #2c7bb6;
    }}

    @media (max-width: 600px) {{
      .card-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="page-header">
    <h1>{contest_name}</h1>
    <p class="subtitle">Analysis &amp; Visualizations</p>
    <div class="badges">{badge_html}</div>
  </div>

  <div class="page-content">
    {tool_section}
    {chart_section}
    {stats_section}
  </div>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Generate contest analysis landing page')
    parser.add_argument('--html-dir',     required=True, help='Directory containing output HTML files')
    parser.add_argument('--charts-dir',   required=True, help='Charts directory (for thumbnails)')
    parser.add_argument('--output-html',  required=True, help='Output HTML file path')
    parser.add_argument('--contest-name', required=True)
    parser.add_argument('--contest-id',   required=True)
    parser.add_argument('--meta-db',       default=None)
    parser.add_argument('--qso-db',        default=None)
    parser.add_argument('--host-state',    default='NY', help='Host state/province abbreviation (e.g. NY, BC)')
    parser.add_argument('--host-type',     default='State', help='Term for the host jurisdiction (e.g. State, Province)')
    parser.add_argument('--region-term',   default='County', help='Display term for host regions (e.g. County, District)')
    parser.add_argument('--mobiles',       default=None, help='Path to mobile_stations.json (used to detect no-mobile contests)')
    parser.add_argument('--dx-countries',  type=int, default=None,
                        help='Number of DX countries worked (from official results)')
    args = parser.parse_args()

    html_dir   = Path(args.html_dir)
    charts_dir = Path(args.charts_dir)
    thumbs_dir = charts_dir / 'thumbnails'
    output_html = Path(args.output_html)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    html = generate_landing_html(
        args.contest_name, args.contest_id,
        html_dir, thumbs_dir, output_html,
        meta_db=args.meta_db, qso_db=args.qso_db,
        dx_countries=args.dx_countries,
        host_state=args.host_state,
        host_type=args.host_type,
        region_term=args.region_term,
        mobiles_json=args.mobiles,
    )
    with open(output_html, 'w') as f:
        f.write(html)
    print(f"Landing page saved to {output_html}")


if __name__ == '__main__':
    main()
