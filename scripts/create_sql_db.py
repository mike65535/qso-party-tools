#!/usr/bin/env python3
"""
Create SQL databases from contest log files (Cabrillo format).
Produces: contest_meta.db (station info/categories) and contest_qsos.db (QSO data)
"""

import sqlite3
import sys
from pathlib import Path


class ContestDatabaseCreator:
    def __init__(self, logs_dir, output_dir):
        self.logs_dir = Path(logs_dir)
        self.output_dir = Path(output_dir)

    def create_meta_db(self):
        """Create database for station metadata and categories."""
        db_path = self.output_dir / 'contest_meta.db'
        if db_path.exists():
            db_path.unlink()

        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS stations (
                callsign TEXT PRIMARY KEY,
                category TEXT,
                operator_category TEXT,
                station_type TEXT,
                transmitter_category TEXT,
                power TEXT,
                band TEXT,
                mode TEXT,
                overlay TEXT,
                claimed_score INTEGER,
                operators TEXT,
                location TEXT,
                club TEXT,
                created_by TEXT,
                log_file TEXT
            )
        ''')

        for log_file in self.logs_dir.glob('*.log'):
            metadata = self.parse_metadata(log_file)
            callsign = metadata.get('callsign', log_file.stem.upper())
            conn.execute('''
                INSERT OR REPLACE INTO stations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                callsign,
                metadata.get('category'),
                metadata.get('operator_category'),
                metadata.get('station_type'),
                metadata.get('transmitter_category'),
                metadata.get('power'),
                metadata.get('band'),
                metadata.get('mode'),
                metadata.get('overlay'),
                metadata.get('claimed_score'),
                metadata.get('operators'),
                metadata.get('location'),
                metadata.get('club'),
                metadata.get('created_by'),
                log_file.name
            ))

        conn.commit()
        conn.close()
        print(f"Created {db_path}")

    def create_qso_db(self):
        """Create database for QSO data."""
        db_path = self.output_dir / 'contest_qsos.db'
        if db_path.exists():
            db_path.unlink()

        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS qsos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_call TEXT,
                freq TEXT,
                mode TEXT,
                date TEXT,
                time TEXT,
                datetime TEXT,
                tx_call TEXT,
                tx_rst TEXT,
                tx_county TEXT,
                rx_call TEXT,
                rx_rst TEXT,
                rx_county TEXT,
                log_file TEXT
            )
        ''')

        for log_file in self.logs_dir.glob('*.log'):
            metadata = self.parse_metadata(log_file)
            station_call = metadata.get('callsign', log_file.stem.upper())

            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('QSO:'):
                        qso = self.parse_qso_line(line)
                        if qso:
                            dt_str = f"{qso['date']} {qso['time'][:2]}:{qso['time'][2:4]}:00"
                            conn.execute('''
                                INSERT INTO qsos VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                station_call,
                                qso['freq'],
                                qso['mode'],
                                qso['date'],
                                qso['time'],
                                dt_str,
                                qso['tx_call'],
                                qso['tx_rst'],
                                qso['tx_county'],
                                qso['rx_call'],
                                qso['rx_rst'],
                                qso['rx_county'],
                                log_file.name
                            ))

        conn.commit()
        conn.close()
        print(f"Created {db_path}")

    def parse_metadata(self, log_file):
        """Extract metadata from Cabrillo log file header."""
        metadata = {}

        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if line.startswith('QSO:'):
                    break
                if ':' not in line:
                    continue

                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()

                field_map = {
                    'category': 'category',
                    'category-operator': 'operator_category',
                    'category-station': 'station_type',
                    'category-power': 'power',
                    'category-band': 'band',
                    'category-mode': 'mode',
                    'category-transmitter': 'transmitter_category',
                    'category-overlay': 'overlay',
                    'operators': 'operators',
                    'location': 'location',
                    'club': 'club',
                    'created-by': 'created_by',
                    'callsign': 'callsign',
                }

                if key in field_map:
                    metadata[field_map[key]] = value
                elif key == 'claimed-score':
                    try:
                        metadata['claimed_score'] = int(value)
                    except ValueError:
                        metadata['claimed_score'] = None

        return metadata

    def parse_qso_line(self, line):
        """Parse Cabrillo QSO line."""
        parts = line.split()
        if len(parts) < 11:
            return None

        return {
            'freq': parts[1],
            'mode': parts[2],
            'date': parts[3],
            'time': parts[4],
            'tx_call': parts[5].rstrip('/M').rstrip('-M'),
            'tx_rst': parts[6],
            'tx_county': parts[7],
            'rx_call': parts[8],
            'rx_rst': parts[9],
            'rx_county': parts[10]
        }

    def create_databases(self):
        """Create both databases."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print("Creating metadata database...")
        self.create_meta_db()
        print("Creating QSO database...")
        self.create_qso_db()
        print("Done!")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: create_sql_db.py <logs_dir> <output_dir>")
        print("  logs_dir   - directory containing .log files")
        print("  output_dir - directory where databases will be written")
        sys.exit(1)

    creator = ContestDatabaseCreator(sys.argv[1], sys.argv[2])
    creator.create_databases()
