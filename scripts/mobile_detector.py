#!/usr/bin/env python3
"""
Mobile Station Detector
Identifies mobile stations from QSO database using metadata + pattern analysis.
"""

import sqlite3
import json
from typing import Dict, List, Set
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class MobileStation:
    """Mobile station metadata"""
    callsign: str
    total_qsos: int
    counties: List[str]
    first_qso: str  # ISO timestamp
    last_qso: str   # ISO timestamp
    icon: str
    is_active: bool


class MobileDetector:
    """Detects mobile stations from QSO database"""

    def __init__(self,
                 min_counties: int = 2,
                 min_qsos: int = 10,
                 host_counties: Set[str] = None):
        self.min_counties = min_counties
        self.min_qsos = min_qsos
        self.host_counties = host_counties or set()

        self.default_icons = {
            'N2CU': '🚗', 'K2A': '🚙', 'N2T': '🚐', 'K2V': '🚕', 'K2Q': '🚓',
            'N1GBE': '🚑', 'WI2M': '🚒', 'W1WV': '🚚', 'N2B': '🚛', 'KQ2R': '🏎️',
            'KV2X': '🚜', 'WT2X': '🛻', 'AB1BL': '🚌'
        }

    def detect_mobiles(self, qso_db_path: str) -> Dict[str, MobileStation]:
        """Detect mobile stations from database using metadata + pattern analysis"""
        conn = sqlite3.connect(qso_db_path)
        cursor = conn.cursor()

        # Try to get stations declared as MOBILE in metadata
        mobile_callsigns = set()
        try:
            meta_db_path = qso_db_path.replace('contest_qsos.db', 'contest_meta.db')
            meta_conn = sqlite3.connect(meta_db_path)
            meta_cursor = meta_conn.cursor()
            meta_cursor.execute("""
                SELECT callsign FROM stations WHERE station_type = 'MOBILE'
            """)
            for (callsign,) in meta_cursor.fetchall():
                mobile_callsigns.add(callsign.split('/')[0])
            meta_conn.close()
            print(f"Found {len(mobile_callsigns)} stations declared as MOBILE in metadata")
        except Exception as e:
            print(f"Could not access metadata ({e}), falling back to pattern analysis")

        county_filter = self.host_counties if self.host_counties else None

        if mobile_callsigns:
            placeholders = ','.join('?' * len(mobile_callsigns))
            if county_filter:
                county_placeholders = ','.join('?' * len(county_filter))
                query = f"""
                SELECT tx_call, COUNT(*) as total_qsos,
                       COUNT(DISTINCT tx_county) as county_count,
                       GROUP_CONCAT(DISTINCT tx_county) as counties,
                       MIN(datetime) as first_qso, MAX(datetime) as last_qso
                FROM qsos
                WHERE tx_call IN ({placeholders})
                  AND tx_county IN ({county_placeholders})
                GROUP BY tx_call
                HAVING county_count >= ? AND total_qsos >= ?
                ORDER BY tx_call
                """
                params = list(mobile_callsigns) + list(county_filter) + [self.min_counties, self.min_qsos]
            else:
                query = f"""
                SELECT tx_call, COUNT(*) as total_qsos,
                       COUNT(DISTINCT tx_county) as county_count,
                       GROUP_CONCAT(DISTINCT tx_county) as counties,
                       MIN(datetime) as first_qso, MAX(datetime) as last_qso
                FROM qsos
                WHERE tx_call IN ({placeholders})
                GROUP BY tx_call
                HAVING county_count >= ? AND total_qsos >= ?
                ORDER BY tx_call
                """
                params = list(mobile_callsigns) + [self.min_counties, self.min_qsos]
        else:
            # Fallback: pattern analysis — any station in 2+ counties with enough QSOs
            if county_filter:
                county_placeholders = ','.join('?' * len(county_filter))
                query = f"""
                SELECT tx_call, COUNT(*) as total_qsos,
                       COUNT(DISTINCT tx_county) as county_count,
                       GROUP_CONCAT(DISTINCT tx_county) as counties,
                       MIN(datetime) as first_qso, MAX(datetime) as last_qso
                FROM qsos
                WHERE tx_county IN ({county_placeholders})
                GROUP BY tx_call
                HAVING county_count >= ? AND total_qsos >= ?
                ORDER BY tx_call
                """
                params = list(county_filter) + [self.min_counties, self.min_qsos]
            else:
                query = """
                SELECT tx_call, COUNT(*) as total_qsos,
                       COUNT(DISTINCT tx_county) as county_count,
                       GROUP_CONCAT(DISTINCT tx_county) as counties,
                       MIN(datetime) as first_qso, MAX(datetime) as last_qso
                FROM qsos
                GROUP BY tx_call
                HAVING county_count >= ? AND total_qsos >= ?
                ORDER BY tx_call
                """
                params = [self.min_counties, self.min_qsos]

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        mobiles = {}
        for row in rows:
            callsign, total_qsos, county_count, counties_str, first_qso, last_qso = row
            counties = sorted(counties_str.split(','))
            icon = self.default_icons.get(callsign, '📍')
            mobiles[callsign] = MobileStation(
                callsign=callsign,
                total_qsos=total_qsos,
                counties=counties,
                first_qso=first_qso,
                last_qso=last_qso,
                icon=icon,
                is_active=True
            )

        return mobiles

    def generate_qc_report(self, mobiles: Dict[str, MobileStation], output_path: str):
        """Generate QC report for mobile station detection"""
        lines = [
            "MOBILE STATION DETECTION QC REPORT",
            "=" * 50,
            f"Detection criteria:",
            f"  1. Declared as MOBILE in contest metadata (or pattern analysis fallback)",
            f"  2. Operated from host-state counties (minimum {self.min_counties})",
            f"  3. Minimum QSOs: {self.min_qsos}",
            "",
            f"Mobile stations detected: {len(mobiles)}",
            "",
            "-" * 80,
            f"{'Callsign':<10} {'QSOs':<6} {'Counties':<4} {'County List':<30} {'Icon':<4}",
            "-" * 80,
        ]

        for callsign, mobile in sorted(mobiles.items()):
            county_list = ','.join(mobile.counties[:5])
            if len(mobile.counties) > 5:
                county_list += f"... (+{len(mobile.counties)-5})"
            lines.append(f"{callsign:<10} {mobile.total_qsos:<6} {len(mobile.counties):<4} "
                         f"{county_list:<30} {mobile.icon:<4}")

        lines += ["-" * 80, "", "ACTIVITY TIMELINE:", ""]
        for callsign, mobile in sorted(mobiles.items()):
            lines.append(f"{callsign}: {mobile.first_qso} to {mobile.last_qso}")

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

    def save_table(self, mobiles: Dict[str, MobileStation], output_path: str):
        """Save mobile stations table as JSON"""
        table = {callsign: asdict(mobile) for callsign, mobile in mobiles.items()}
        with open(output_path, 'w') as f:
            json.dump(table, f, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Detect mobile stations from QSO database')
    parser.add_argument('--db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--verbose', action='store_true', help='Also generate QC report')
    parser.add_argument('--min-counties', type=int, default=2)
    parser.add_argument('--min-qsos', type=int, default=10)
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    detector = MobileDetector(min_counties=args.min_counties, min_qsos=args.min_qsos)
    print(f"Detecting mobile stations from {args.db}...")
    mobiles = detector.detect_mobiles(args.db)
    print(f"Found {len(mobiles)} mobile stations")

    detector.save_table(mobiles, args.output)
    print(f"Saved to {args.output}")

    if args.verbose:
        qc_path = args.output.replace('.json', '_qc.txt')
        detector.generate_qc_report(mobiles, qc_path)
        print(f"QC report saved to {qc_path}")

    for callsign, mobile in sorted(mobiles.items()):
        print(f"  {callsign}: {mobile.total_qsos} QSOs across {len(mobile.counties)} counties")


if __name__ == "__main__":
    main()
