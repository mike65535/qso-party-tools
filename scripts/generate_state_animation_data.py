#!/usr/bin/env python3
"""
Generate state-level QSO animation data (JSON).
Produces 1-minute interval cumulative QSO counts per state for the US state animation.
"""

import sqlite3
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path


# Default NY county abbreviations — used to map tx_county to state code 'NY'
DEFAULT_HOST_COUNTIES = {
    'ALB', 'ALL', 'BRM', 'BRX', 'CAT', 'CAY', 'CHA', 'CHE', 'CGO', 'CLI',
    'COL', 'COR', 'DEL', 'DUT', 'ERI', 'ESS', 'FRA', 'FUL', 'GEN', 'GRE',
    'HAM', 'HER', 'JEF', 'KIN', 'LEW', 'LIV', 'MAD', 'MON', 'MTG', 'NAS',
    'NEW', 'NIA', 'ONE', 'ONO', 'ONT', 'ORA', 'ORL', 'OSW', 'OTS', 'PUT',
    'QUE', 'REN', 'RIC', 'ROC', 'SAR', 'SCH', 'SCO', 'SCU', 'SEN', 'STE',
    'STL', 'SUF', 'SUL', 'TIO', 'TOM', 'ULS', 'WAR', 'WAS', 'WAY', 'WES',
    'WYO', 'YAT',
}


def generate_state_animation_data(qso_db, output_file, contest_start_str,
                                   contest_end_str, host_state, host_counties):
    host_counties_upper = {c.upper() for c in host_counties}
    host_state = host_state.upper()

    fmt = '%Y-%m-%dT%H:%M:%S' if 'T' in contest_start_str else '%Y-%m-%d %H:%M:%S'
    start_time = datetime.strptime(contest_start_str, fmt)
    end_time   = datetime.strptime(contest_end_str,   fmt)
    print(f"Using contest window: {start_time} to {end_time}")

    conn = sqlite3.connect(qso_db)
    cursor = conn.cursor()

    # Build SQL CASE clause to map host counties -> host state
    county_list = "','".join(sorted(host_counties_upper))
    query = f"""
    SELECT datetime, station_call, tx_county,
        CASE WHEN UPPER(tx_county) IN ('{county_list}') THEN '{host_state}'
             ELSE UPPER(tx_county)
        END as state
    FROM valid_qsos
    WHERE datetime >= ? AND datetime <= ?
    ORDER BY datetime
    """

    cursor.execute(query, (start_time.strftime('%Y-%m-%d %H:%M:%S'),
                           end_time.strftime('%Y-%m-%d %H:%M:%S')))
    qsos = cursor.fetchall()
    conn.close()
    print(f"Processing {len(qsos)} QSOs for state animation...")

    # Bin into 1-minute intervals
    state_data = {}
    for qso_time_str, station, county, state in qsos:
        qso_time = datetime.strptime(qso_time_str, '%Y-%m-%d %H:%M:%S')
        minutes_elapsed = int((qso_time - start_time).total_seconds() / 60)
        interval_time = start_time + timedelta(minutes=minutes_elapsed)
        time_key = interval_time.strftime('%H:%M')

        if time_key not in state_data:
            state_data[time_key] = {}
        state_data[time_key][state] = state_data[time_key].get(state, 0) + 1

    # Build cumulative animation frames
    animation_frames = []
    cumulative_counts = {}
    current = start_time

    while current < end_time:
        time_key = current.strftime('%H:%M')
        if current != start_time and time_key in state_data:
            for state, count in state_data[time_key].items():
                cumulative_counts[state] = cumulative_counts.get(state, 0) + count

        animation_frames.append({
            'time': time_key,
            'date': current.strftime('%Y-%m-%d'),
            'states': dict(cumulative_counts)
        })
        current += timedelta(minutes=1)

    output_data = {
        'frames': animation_frames,
        'total_qsos': len(qsos),
        'contest_start': contest_start_str,
        'contest_end': contest_end_str,
        'host_state': host_state,
    }

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"State animation data saved to {output_file}")
    print(f"  Frames: {len(animation_frames)}")
    print(f"  States with activity: {len(cumulative_counts)}")
    return output_data


def main():
    parser = argparse.ArgumentParser(description='Generate state-level QSO animation data')
    parser.add_argument('--db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--contest-start', required=True,
                        help='Contest start UTC (e.g. "2025-10-18 14:00:00")')
    parser.add_argument('--contest-end', required=True,
                        help='Contest end UTC (e.g. "2025-10-19 02:00:00")')
    parser.add_argument('--host-state', default='NY',
                        help='Host state abbreviation (default: NY)')
    parser.add_argument('--host-counties', help='JSON file with host county abbreviations list '
                        '(uses NY defaults if omitted)')
    args = parser.parse_args()

    host_counties = DEFAULT_HOST_COUNTIES
    if args.host_counties:
        with open(args.host_counties, 'r') as f:
            host_counties = set(json.load(f))

    generate_state_animation_data(
        args.db, args.output,
        args.contest_start, args.contest_end,
        args.host_state, host_counties
    )


if __name__ == "__main__":
    main()
