#!/usr/bin/env python3
"""
Contest processing pipeline orchestrator.
Reads a contest config JSON and runs all scripts in sequence.

Usage:
    python3 scripts/process_contest.py config/nyqp_2025.json <logs_dir>

Directory layout (relative to repo root):
    data/<contest_id>/          - databases
    outputs/<contest_id>/       - generated outputs
      charts/                   - PNG charts and thumbnails
      html/                     - HTML maps and stats
      stats/                    - QC reports and JSON data files
"""

import json
import sys
import subprocess
from pathlib import Path


def run(script, args, script_dir):
    """Run a script from the scripts/ directory, exit on failure."""
    cmd = [sys.executable, str(script_dir / script)] + [str(a) for a in args]
    print(f"\n>>> {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: {script} failed (exit {result.returncode})")
        sys.exit(1)


def main():
    if len(sys.argv) < 3:
        print("Usage: process_contest.py <config.json> <logs_dir>")
        print("  config.json  - contest config file (e.g. config/nyqp_2025.json)")
        print("  logs_dir     - directory containing .log files")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    logs_dir = Path(sys.argv[2])

    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    if not logs_dir.is_dir():
        print(f"Logs directory not found: {logs_dir}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    contest_id = config['contest_id']
    contest_name = f"{config['year']} {config['name']}"
    contest_start = f"{config['schedule']['date']} {config['schedule']['start_time'].replace('Z', '')}"
    duration_hours = config['schedule']['duration_hours']

    # Derived paths
    repo_root = Path(__file__).parent.parent
    script_dir = repo_root / 'scripts'
    data_dir = repo_root / 'data' / contest_id
    output_dir = repo_root / 'outputs' / contest_id
    charts_dir = output_dir / 'charts'
    html_dir = output_dir / 'html'
    stats_dir = output_dir / 'stats'

    meta_db = data_dir / 'contest_meta.db'
    qso_db = data_dir / 'contest_qsos.db'
    normalizations_json = data_dir / 'callsign_normalizations.json'
    mobiles_json = stats_dir / 'mobile_stations.json'
    county_counts_json = stats_dir / 'county_qso_counts_all.json'
    county_line_json = stats_dir / 'county_line_periods.json'
    state_anim_json = stats_dir / 'state_qso_animation_data.json'
    enhanced_map_html = html_dir / f'{contest_id}_enhanced_map.html'
    county_anim_html = html_dir / f'{contest_id}_county_animation.html'
    mobile_anim_html = html_dir / f'{contest_id}_mobile_animation.html'
    state_anim_html = html_dir / f'{contest_id}_state_animation.html'

    for d in [data_dir, charts_dir, html_dir, stats_dir]:
        d.mkdir(parents=True, exist_ok=True)

    print(f"=== Processing: {contest_name} ===")
    print(f"  Logs:    {logs_dir}")
    print(f"  Data:    {data_dir}")
    print(f"  Outputs: {output_dir}")

    # 1. Build databases
    print("\n[1/11] Creating databases...")
    run('create_sql_db.py', [logs_dir, data_dir], script_dir)

    # 2. Detect mobile stations
    print("\n[2/11] Detecting mobile stations...")
    run('mobile_detector.py', [
        '--db', qso_db,
        '--output', mobiles_json,
        '--verbose'
    ], script_dir)

    # 3. Generate county-line periods
    print("\n[3/11] Generating county-line periods...")
    run('county_line_periods.py', [
        '--db', qso_db,
        '--mobiles', mobiles_json,
        '--output', county_line_json,
        '--verbose'
    ], script_dir)

    # 4. Generate county QSO counts
    print("\n[4/11] Generating county QSO counts...")
    run('county_qso_counts.py', [
        '--db', qso_db,
        '--filter', 'all',
        '--output', county_counts_json,
        '--verbose'
    ], script_dir)

    # 5. Generate charts
    print("\n[5/11] Generating analysis charts...")
    run('create_charts.py', [
        '--meta-db', meta_db,
        '--qso-db', qso_db,
        '--output-dir', charts_dir,
        '--contest-id', contest_id.upper().replace('-', '_'),
        '--contest-start', contest_start,
        '--duration-hours', duration_hours
    ], script_dir)

    # 6. Generate thumbnails
    print("\n[6/11] Generating chart thumbnails...")
    run('create_thumbnails.py', [
        '--charts-dir', charts_dir
    ], script_dir)

    # Derive contest ISO timestamps (used by stats and animations)
    schedule = config['schedule']
    contest_start_iso = f"{schedule['date']}T{schedule['start_time'].replace('Z', '')}"
    end_date_offset = schedule.get('end_date_offset', 0)
    if end_date_offset:
        from datetime import date, timedelta
        end_date = (date.fromisoformat(schedule['date']) + timedelta(days=end_date_offset)).isoformat()
    else:
        end_date = schedule['date']
    contest_end_iso = f"{end_date}T{schedule['end_time'].replace('Z', '')}"

    # 7. Generate contest stats
    print("\n[7/11] Generating contest statistics...")
    run('generate_stats.py', [
        '--meta-db', meta_db,
        '--qso-db', qso_db,
        '--output-dir', html_dir,
        '--contest-name', contest_name,
        '--contest-start', contest_start_iso,
        '--contest-end', contest_end_iso,
        '--normalizations', normalizations_json,
        '--mobiles', mobiles_json,
    ], script_dir)

    # 8. Generate enhanced map
    print("\n[8/11] Generating enhanced county map...")
    ny_boundaries = repo_root / 'reference' / 'ny_counties.json'
    run('generate_enhanced_map.py', [
        '--meta-db', meta_db,
        '--qso-db', qso_db,
        '--output', enhanced_map_html,
        '--boundaries', ny_boundaries,
        '--title', f'QSOs made from {config.get("host_state", "host")} stations'
    ], script_dir)

    # 9. Generate county-level animation
    print("\n[9/11] Generating county activity animation...")
    run('generate_county_animation_html.py', [
        '--db', qso_db,
        '--boundaries', ny_boundaries,
        '--output', county_anim_html,
        '--contest-start', contest_start_iso,
        '--contest-end', contest_end_iso,
        '--title', f'{contest_name} County Activity'
    ], script_dir)

    # 10. Generate mobile animation
    print("\n[10/11] Generating mobile station animation...")
    run('generate_mobile_animation_html.py', [
        '--db', qso_db,
        '--mobiles', mobiles_json,
        '--county-line-periods', county_line_json,
        '--boundaries', ny_boundaries,
        '--output', mobile_anim_html,
        '--contest-start', contest_start_iso,
        '--contest-end', contest_end_iso,
        '--title', f'{contest_name} Mobile Activity'
    ], script_dir)

    # 11. Generate state-level animation (requires US boundaries)
    us_boundaries = repo_root / 'reference' / 'us_states.json'
    if us_boundaries.exists():
        print("\n[11/11] Generating US state animation...")
        run('generate_state_animation_data.py', [
            '--db', qso_db,
            '--output', state_anim_json,
            '--contest-start', contest_start.replace('T', ' '),
            '--contest-end', contest_end_iso.replace('T', ' '),
            '--host-state', config.get('host_state', 'NY')
        ], script_dir)
        run('generate_state_animation_html.py', [
            '--animation-data', state_anim_json,
            '--boundaries', us_boundaries,
            '--output', state_anim_html,
            '--host-state', config.get('host_state', 'NY'),
            '--contest-name', contest_name
        ], script_dir)
    else:
        print("\n[11/11] Skipping US state animation (reference/us_states.json not found)")

    print(f"\n=== Done! Outputs in {output_dir} ===")


if __name__ == '__main__':
    main()
