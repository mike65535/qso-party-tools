#!/usr/bin/env python3
"""
County Line Period Generator
Detects county-line operation periods from mobile station QSO sequences.
"""

import sqlite3
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class CountyLinePeriod:
    start_time: str
    end_time: str
    counties: List[str]
    qso_count: int
    alternations: int
    start_idx: int
    end_idx: int


@dataclass
class QSORecord:
    timestamp: datetime
    tx_county: str
    qso_id: int


class CountyLinePeriodGenerator:

    def __init__(self, min_alternations: int = 3, max_consecutive_same: int = 2):
        self.min_alternations = min_alternations
        self.max_consecutive_same = max_consecutive_same

    def load_mobile_qsos(self, db_path: str, callsign: str) -> List[QSORecord]:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, datetime, tx_county FROM valid_qsos WHERE tx_call = ? ORDER BY datetime",
            (callsign,)
        )
        rows = cursor.fetchall()
        conn.close()

        qsos = []
        for qso_id, datetime_str, tx_county in rows:
            timestamp = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            qsos.append(QSORecord(timestamp, tx_county, qso_id))
        return qsos

    def find_county_line_periods(self, qsos: List[QSORecord]) -> List[CountyLinePeriod]:
        if len(qsos) < self.min_alternations + 1:
            return []

        periods = []
        i = 0
        while i < len(qsos) - self.min_alternations:
            period = self._detect_period_from(qsos, i)
            if period:
                periods.append(period)
                i = period.end_idx + 1
            else:
                i += 1
        return periods

    def _detect_period_from(self, qsos: List[QSORecord], start_idx: int) -> Optional[CountyLinePeriod]:
        if start_idx + self.min_alternations >= len(qsos):
            return None

        scan_window = min(start_idx + 10, len(qsos))
        county_pair = self._find_alternating_pair(qsos[start_idx:scan_window])
        if not county_pair:
            return None

        county_a, county_b = county_pair
        end_idx, alternations = self._trace_pattern(qsos, start_idx, county_a, county_b)

        if alternations >= self.min_alternations:
            return CountyLinePeriod(
                start_time=qsos[start_idx].timestamp.isoformat(),
                end_time=qsos[end_idx].timestamp.isoformat(),
                counties=sorted([county_a, county_b]),
                qso_count=end_idx - start_idx + 1,
                alternations=alternations,
                start_idx=start_idx,
                end_idx=end_idx
            )
        return None

    def _find_alternating_pair(self, qsos: List[QSORecord]) -> Optional[tuple]:
        for i in range(len(qsos) - 2):
            a = qsos[i].tx_county
            b = qsos[i + 1].tx_county
            if a == b:
                continue
            if i + 2 < len(qsos) and qsos[i + 2].tx_county == a:
                return (a, b)
        return None

    def _trace_pattern(self, qsos: List[QSORecord], start_idx: int,
                       county_a: str, county_b: str) -> tuple:
        expected = qsos[start_idx].tx_county
        if expected not in (county_a, county_b):
            return (start_idx, 0)

        alternations = 0
        consecutive_same = 0
        last_valid_idx = start_idx

        for i in range(start_idx, len(qsos)):
            current = qsos[i].tx_county
            if current not in (county_a, county_b):
                break
            if current == expected:
                consecutive_same = 0
                last_valid_idx = i
                expected = county_b if expected == county_a else county_a
                alternations += 1
            else:
                consecutive_same += 1
                last_valid_idx = i
                if consecutive_same > self.max_consecutive_same:
                    last_valid_idx = i - consecutive_same
                    break

        return (last_valid_idx, alternations)

    def generate_periods_table(self, db_path: str, mobile_stations: List[str]) -> Dict[str, List[CountyLinePeriod]]:
        periods_table = {}
        for callsign in mobile_stations:
            qsos = self.load_mobile_qsos(db_path, callsign)
            periods = self.find_county_line_periods(qsos)
            if periods:
                periods_table[callsign] = periods
        return periods_table

    def generate_qc_report(self, periods_table: Dict[str, List[CountyLinePeriod]], output_path: str):
        total_periods = sum(len(p) for p in periods_table.values())
        lines = [
            "COUNTY LINE PERIODS QC REPORT",
            "=" * 50,
            f"Parameters: min_alternations={self.min_alternations}, max_consecutive_same={self.max_consecutive_same}",
            "",
            f"Stations with county-line periods: {len(periods_table)}",
            f"Total periods detected: {total_periods}",
            "",
            "-" * 100,
            f"{'Station':<8} {'#':<3} {'Start':<16} {'End':<16} {'Counties':<8} {'QSOs':<5} {'Alt':<4} {'Dur':<8}",
            "-" * 100,
        ]

        for callsign, periods in sorted(periods_table.items()):
            for i, period in enumerate(periods, 1):
                start_dt = datetime.fromisoformat(period.start_time)
                end_dt = datetime.fromisoformat(period.end_time)
                duration = (end_dt - start_dt).total_seconds() / 60
                counties_str = '/'.join(period.counties)
                lines.append(
                    f"{callsign:<8} {i:<3} {start_dt.strftime('%m-%d %H:%M'):<16} "
                    f"{end_dt.strftime('%m-%d %H:%M'):<16} {counties_str:<8} "
                    f"{period.qso_count:<5} {period.alternations:<4} {duration:>6.0f}m"
                )

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

    def save_table(self, periods_table: Dict[str, List[CountyLinePeriod]], output_path: str):
        serializable = {
            callsign: [asdict(p) for p in periods]
            for callsign, periods in periods_table.items()
        }
        with open(output_path, 'w') as f:
            json.dump(serializable, f, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate county-line periods table')
    parser.add_argument('--db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--mobiles', required=True, help='Path to mobile_stations.json')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--verbose', action='store_true', help='Also generate QC report')
    parser.add_argument('--min-alternations', type=int, default=3)
    parser.add_argument('--max-consecutive', type=int, default=2)
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    with open(args.mobiles, 'r') as f:
        mobile_data = json.load(f)
    mobile_stations = list(mobile_data.keys())
    print(f"Processing {len(mobile_stations)} mobile stations...")

    generator = CountyLinePeriodGenerator(
        min_alternations=args.min_alternations,
        max_consecutive_same=args.max_consecutive
    )
    periods_table = generator.generate_periods_table(args.db, mobile_stations)

    total_periods = sum(len(p) for p in periods_table.values())
    print(f"Found county-line periods for {len(periods_table)} stations ({total_periods} total)")

    generator.save_table(periods_table, args.output)
    print(f"Saved to {args.output}")

    if args.verbose:
        qc_path = args.output.replace('.json', '_qc.txt')
        generator.generate_qc_report(periods_table, qc_path)
        print(f"QC report saved to {qc_path}")


if __name__ == "__main__":
    main()
