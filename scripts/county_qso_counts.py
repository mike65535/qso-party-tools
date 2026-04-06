#!/usr/bin/env python3
"""
County QSO Count Generator
Generates QSO counts per county for choropleth map visualization.
Supports filtering by all stations, mobile-only, fixed-only, or a custom list.
"""

import sqlite3
import json
from typing import Dict, List, Optional
from pathlib import Path


class CountyQSOCounter:

    def get_qso_counts_by_filter(self, db_path: str,
                                 filter_type: str = "all",
                                 station_list: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Get QSO counts per county.

        filter_type: "all" | "mobile_only" | "fixed_only" | "station_list"
        station_list: required for mobile_only, fixed_only, station_list
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if filter_type == "all":
            cursor.execute("""
                SELECT tx_county, COUNT(*) FROM qsos GROUP BY tx_county ORDER BY COUNT(*) DESC
            """)

        elif filter_type in ("mobile_only", "station_list") and station_list:
            placeholders = ','.join('?' * len(station_list))
            cursor.execute(f"""
                SELECT tx_county, COUNT(*) FROM qsos
                WHERE tx_call IN ({placeholders})
                GROUP BY tx_county ORDER BY COUNT(*) DESC
            """, station_list)

        elif filter_type == "fixed_only" and station_list:
            placeholders = ','.join('?' * len(station_list))
            cursor.execute(f"""
                SELECT tx_county, COUNT(*) FROM qsos
                WHERE tx_call NOT IN ({placeholders})
                GROUP BY tx_county ORDER BY COUNT(*) DESC
            """, station_list)

        else:
            conn.close()
            raise ValueError(f"Invalid filter_type '{filter_type}' or missing station_list")

        rows = cursor.fetchall()
        conn.close()
        return {county: count for county, count in rows}

    def generate_qc_report(self, county_counts: Dict[str, int], output_path: str,
                           title: str = "County QSO Counts"):
        counts = list(county_counts.values())
        sorted_counties = sorted(county_counts.items(), key=lambda x: x[1], reverse=True)

        lines = [
            f"{title.upper()} QC REPORT",
            "=" * 50,
            f"Counties with QSOs: {len(county_counts)}",
            f"Total QSOs: {sum(counts)}",
            "",
            "TOP 20 COUNTIES:",
            "-" * 30,
            f"{'County':<8} {'QSOs':<8}",
            "-" * 30,
        ]
        for county, count in sorted_counties[:20]:
            lines.append(f"{county:<8} {count:<8}")
        if len(sorted_counties) > 20:
            lines.append(f"... and {len(sorted_counties) - 20} more")

        lines += [
            "",
            "STATISTICS:",
            f"  Max: {max(counts)}",
            f"  Min: {min(counts)}",
            f"  Average: {sum(counts) / len(counts):.1f}",
            f"  Median: {sorted(counts)[len(counts)//2]}",
        ]

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

    def save_table(self, county_counts: Dict[str, int], output_path: str):
        with open(output_path, 'w') as f:
            json.dump(county_counts, f, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate county QSO count table')
    parser.add_argument('--db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--filter', choices=['all', 'mobile_only', 'fixed_only'], default='all')
    parser.add_argument('--mobiles', help='Path to mobile_stations.json (for mobile/fixed filters)')
    parser.add_argument('--output', help='Output JSON path (auto-named if omitted)')
    parser.add_argument('--verbose', action='store_true', help='Also generate QC report')
    args = parser.parse_args()

    if not args.output:
        suffix = {'all': 'all', 'mobile_only': 'mobile', 'fixed_only': 'fixed'}[args.filter]
        args.output = f'outputs/county_qso_counts_{suffix}.json'

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    mobile_stations = None
    if args.mobiles and args.filter in ('mobile_only', 'fixed_only'):
        with open(args.mobiles, 'r') as f:
            mobile_stations = list(json.load(f).keys())

    counter = CountyQSOCounter()
    county_counts = counter.get_qso_counts_by_filter(args.db, args.filter, mobile_stations)
    print(f"Found QSOs in {len(county_counts)} counties ({sum(county_counts.values())} total)")

    counter.save_table(county_counts, args.output)
    print(f"Saved to {args.output}")

    if args.verbose:
        qc_path = args.output.replace('.json', '_qc.txt')
        title = {'all': 'All', 'mobile_only': 'Mobile', 'fixed_only': 'Fixed'}[args.filter]
        counter.generate_qc_report(county_counts, qc_path, f"{title} County QSO Counts")
        print(f"QC report saved to {qc_path}")

    for county, count in sorted(county_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {county}: {count}")


if __name__ == "__main__":
    main()
