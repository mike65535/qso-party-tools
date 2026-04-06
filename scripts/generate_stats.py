#!/usr/bin/env python3
"""
Generate contest statistics HTML and JSON summary.
"""

import sqlite3
import json
import argparse
from pathlib import Path


def generate_contest_stats(meta_db, qso_db):
    """Generate summary statistics from the databases."""
    stats = {}
    meta_conn = sqlite3.connect(meta_db)

    stats['total_logs'] = meta_conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
    stats['unique_callsigns'] = meta_conn.execute("SELECT COUNT(DISTINCT callsign) FROM stations").fetchone()[0]

    ny_count = meta_conn.execute("SELECT COUNT(*) FROM stations WHERE location = 'NY'").fetchone()[0]
    stats['ny_stations'] = ny_count
    stats['non_ny_stations'] = stats['total_logs'] - ny_count

    # Official overlay categories
    overlay_counts = {}
    for overlay in ['ROOKIE', 'YOUTH12', 'YOUTH17', 'YL']:
        count = meta_conn.execute("SELECT COUNT(*) FROM stations WHERE overlay = ?", (overlay,)).fetchone()[0]
        if count > 0:
            overlay_counts[overlay] = count
    stats['official_overlays'] = overlay_counts

    # Unofficial overlays
    unofficial_overlays = {}
    for row in meta_conn.execute(
        "SELECT overlay, COUNT(*) FROM stations "
        "WHERE overlay NOT IN ('ROOKIE','YOUTH12','YOUTH17','YL') "
        "AND overlay IS NOT NULL AND overlay != '' GROUP BY overlay"
    ):
        unofficial_overlays[row[0]] = row[1]
    stats['unofficial_overlays'] = unofficial_overlays

    # Station types, operator categories, power levels
    for field, key in [('station_type', 'station_types'),
                        ('operator_category', 'operator_categories'),
                        ('power', 'power_levels')]:
        result = {}
        for row in meta_conn.execute(
            f"SELECT {field}, COUNT(*) FROM stations "
            f"WHERE {field} IS NOT NULL AND {field} != '' GROUP BY {field}"
        ):
            result[row[0]] = row[1]
        stats[key] = result

    ny_callsigns = [row[0] for row in meta_conn.execute("SELECT callsign FROM stations WHERE location = 'NY'")]
    meta_conn.close()

    qso_conn = sqlite3.connect(qso_db)
    stats['total_qsos'] = qso_conn.execute("SELECT COUNT(*) FROM qsos").fetchone()[0]
    if ny_callsigns:
        placeholders = ','.join('?' * len(ny_callsigns))
        stats['qsos_by_ny'] = qso_conn.execute(
            f"SELECT COUNT(*) FROM qsos WHERE station_call IN ({placeholders})", ny_callsigns
        ).fetchone()[0]
    else:
        stats['qsos_by_ny'] = 0
    qso_conn.close()

    return stats


def format_stats_html(stats, contest_name):
    """Format stats as an HTML fragment."""

    def section(title, items):
        rows = ''.join(f"<li><strong>{k}:</strong> {v:,}</li>\n" for k, v in items.items())
        return f'<div class="stat-section"><h3>{title}</h3><ul>\n{rows}</ul></div>\n'

    html = f'<div class="contest-stats">\n<h2>{contest_name} Statistics</h2>\n'

    html += section("Participation", {
        "Total Logs Submitted": stats['total_logs'],
        "Unique Callsigns": stats['unique_callsigns'],
        "Host-State Stations": stats['ny_stations'],
        "Non-Host-State Stations": stats['non_ny_stations'],
    })

    html += section("QSO Activity", {
        "Total QSOs": stats['total_qsos'],
        "QSOs by Host-State Stations": stats['qsos_by_ny'],
    })

    if stats.get('official_overlays'):
        html += section("Official Overlay Categories", stats['official_overlays'])
    if stats.get('unofficial_overlays'):
        html += section("Unofficial Overlay Categories", stats['unofficial_overlays'])
    if stats.get('station_types'):
        html += section("Station Types", stats['station_types'])
    if stats.get('operator_categories'):
        html += section("Operator Categories", stats['operator_categories'])
    if stats.get('power_levels'):
        html += section("Power Levels", stats['power_levels'])

    html += '</div>'
    return html


def main():
    parser = argparse.ArgumentParser(description='Generate contest statistics')
    parser.add_argument('--meta-db', required=True, help='Path to contest_meta.db')
    parser.add_argument('--qso-db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output-dir', required=True, help='Directory for output files')
    parser.add_argument('--contest-name', required=True, help='Contest display name (e.g. "2025 New York QSO Party")')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = generate_contest_stats(args.meta_db, args.qso_db)

    json_path = output_dir / 'contest_stats.json'
    with open(json_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Saved {json_path}")

    html_path = output_dir / 'contest_stats.html'
    with open(html_path, 'w') as f:
        f.write(format_stats_html(stats, args.contest_name))
    print(f"Saved {html_path}")

    print(f"Total Logs: {stats['total_logs']}")
    print(f"Host-State Stations: {stats['ny_stations']}")
    print(f"Non-Host-State Stations: {stats['non_ny_stations']}")
    print(f"Total QSOs: {stats['total_qsos']:,}")


if __name__ == '__main__':
    main()
