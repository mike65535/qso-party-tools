#!/usr/bin/env python3
"""
Generate contest analysis charts (PNG).
Produces: box plot, QSO distribution, QSO histogram, per-band activity, stacked band charts.
"""

import os
import sqlite3
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from pathlib import Path


def create_score_boxplot(meta_db, qso_db, output_dir, contest_id):
    stations = pd.read_sql_query("""
        SELECT callsign, operator_category, transmitter_category, station_type, power, mode, claimed_score
        FROM stations WHERE operator_category != 'CHECKLOG'
    """, sqlite3.connect(meta_db))

    qso_counts = pd.read_sql_query("""
        SELECT station_call, COUNT(*) as qso_count
        FROM (SELECT DISTINCT station_call, datetime, freq, tx_call, rx_call FROM valid_qsos)
        GROUP BY station_call
    """, sqlite3.connect(qso_db))

    data = pd.merge(stations, qso_counts, left_on='callsign', right_on='station_call', how='left')
    data['score'] = data['qso_count']
    data = data[(data['score'].notna()) & (data['score'] > 0)]

    def abbreviate(row):
        op = {'SINGLE-OP': 'SO'}.get(row['operator_category'],
              'MS' if row['operator_category'] == 'MULTI-OP' and row['transmitter_category'] == 'ONE'
              else 'MM' if row['operator_category'] == 'MULTI-OP' else row['operator_category'])
        pwr = {'HIGH': 'HP', 'LOW': 'LP', 'QRP': 'QRP'}.get(row['power'], row['power'])
        mode = {'SSB': 'PH', 'MIXED': 'MIX', 'CW': 'CW'}.get(row['mode'], row['mode'])
        stn = {'FIXED': 'F', 'PORTABLE': 'P', 'MOBILE': 'M'}.get(row['station_type'], row['station_type'])
        return f"{op}-{pwr}-{mode}-{stn}"

    data['category_id'] = data.apply(abbreviate, axis=1)

    _stn_order  = {'F': 0, 'P': 1, 'M': 2}
    _pwr_order  = {'HP': 0, 'LP': 1, 'QRP': 2}
    _mode_order = {'CW': 0, 'PH': 1, 'MIX': 2}

    def _cat_sort_key(cat):
        parts = cat.split('-')
        # format: OP-PWR-MODE-STN  (may have QRP as 3-char power)
        stn  = parts[-1]
        mode = parts[-2]
        pwr  = '-'.join(parts[1:-2]) if len(parts) > 3 else parts[1] if len(parts) > 1 else ''
        op   = parts[0]
        _op_order = {'MM': 0, 'MS': 1, 'SO': 2}
        return (
            _stn_order.get(stn, 9),
            _op_order.get(op, 9),
            _pwr_order.get(pwr, 9),
            _mode_order.get(mode, 9),
        )

    categories_list = sorted(data['category_id'].unique(), key=_cat_sort_key)
    box_data = [data[data['category_id'] == cat]['score'].values for cat in categories_list]

    plt.figure(figsize=(12, 8))
    plt.boxplot(box_data, tick_labels=categories_list, whis=1.5, showfliers=True)
    plt.title('Box Plot of QSO Count by Category', fontsize=16)
    plt.xlabel('Category', fontsize=12)
    plt.ylabel('QSO Count', fontsize=12)
    plt.xticks(rotation=90, ha='right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f'{contest_id}_BoxPlotOfScoreByCategory.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Created box plot ({len(categories_list)} categories, {len(data)} stations)")


def create_qso_distribution(meta_db, qso_db, output_dir, contest_id, host_state='NY'):
    host_stations = pd.read_sql_query(
        f"SELECT callsign FROM stations WHERE location = '{host_state}'",
        sqlite3.connect(meta_db)
    )['callsign'].tolist()

    qsos = pd.read_sql_query("""
        SELECT DISTINCT station_call, mode, tx_call, rx_call, datetime, freq FROM valid_qsos
    """, sqlite3.connect(qso_db))

    non_host = f'Non-{host_state}'
    qsos['tx_location'] = qsos['tx_call'].apply(
        lambda x: host_state if x in host_stations else non_host
    )
    qsos['mode_clean'] = qsos['mode'].apply(lambda x: 'CW' if 'CW' in x else 'Phone')

    categories = [
        f'{host_state} CW QSOs', f'{host_state} Phone QSOs',
        f'{non_host} CW QSOs',   f'{non_host} Phone QSOs',
    ]
    counts = [
        len(qsos[(qsos['tx_location'] == host_state) & (qsos['mode_clean'] == 'CW')]),
        len(qsos[(qsos['tx_location'] == host_state) & (qsos['mode_clean'] == 'Phone')]),
        len(qsos[(qsos['tx_location'] == non_host)   & (qsos['mode_clean'] == 'CW')]),
        len(qsos[(qsos['tx_location'] == non_host)   & (qsos['mode_clean'] == 'Phone')]),
    ]

    plt.figure(figsize=(10, 6))
    bars = plt.bar(range(len(categories)), counts,
                   color=['#1f77b4', '#17becf', '#e377c2', '#ff7f0e'])
    plt.title('Distribution of QSOs by Location and Mode', fontsize=16)
    plt.xlabel('Location and Mode', fontsize=12)
    plt.ylabel('Number of QSOs', fontsize=12)
    plt.xticks(range(len(categories)), categories, rotation=45, ha='right')
    for bar, value in zip(bars, counts):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(counts)*0.01,
                 f'{value:,}', ha='center', va='bottom')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f'{contest_id}_DistributionOfQSOsByLocationAndMode.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Created QSO distribution chart (total: {sum(counts):,})")


def create_qso_histogram(qso_db, output_dir, contest_id):
    qso_counts = pd.read_sql_query(
        "SELECT station_call, COUNT(*) as qso_total FROM valid_qsos GROUP BY station_call",
        sqlite3.connect(qso_db)
    )
    max_qsos = int(qso_counts['qso_total'].max())
    bin_size = 100
    bins = range(0, max_qsos + bin_size, bin_size)

    plt.figure(figsize=(10, 6))
    plt.hist(qso_counts['qso_total'], bins=bins, color='#1f77b4', alpha=0.7, edgecolor='black')
    plt.title('Histogram of QSO Totals', fontsize=16)
    plt.xlabel('QSO Total', fontsize=12)
    plt.ylabel('Number of Logs', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / f'{contest_id}_HistogramOfQSO_Totals.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("Created QSO histogram")


def _build_interval_data(qso_db):
    """Load QSOs and bin into 15-minute intervals with band and mode columns."""
    qsos = pd.read_sql_query(
        "SELECT DISTINCT station_call, freq, mode, date, time FROM valid_qsos ORDER BY date, time",
        sqlite3.connect(qso_db)
    )

    def freq_to_band(freq_str):
        try:
            freq = int(freq_str)
            if 1800 <= freq <= 2000: return '160m'
            elif 3500 <= freq <= 4000: return '80m'
            elif 7000 <= freq <= 7300: return '40m'
            elif 14000 <= freq <= 14350: return '20m'
            elif 21000 <= freq <= 21450: return '15m'
            elif 28000 <= freq <= 29700: return '10m'
            else: return 'VHF+'
        except Exception:
            return 'Unknown'

    qsos['band'] = qsos['freq'].apply(freq_to_band)
    qsos['mode_clean'] = qsos['mode'].apply(lambda x: 'CW' if x == 'CW' else 'PH')

    qsos['time_minutes'] = qsos['time'].str[:2].astype(int) * 60 + qsos['time'].str[2:4].astype(int)
    qsos['time_15min'] = (qsos['time_minutes'] // 15) * 15
    qsos['time_str'] = (qsos['time_15min'] // 60).astype(str).str.zfill(2) + ':' + \
                       (qsos['time_15min'] % 60).astype(str).str.zfill(2) + ':00'
    qsos['dt'] = pd.to_datetime(qsos['date'] + ' ' + qsos['time_str'], format='%Y-%m-%d %H:%M:%S')

    return qsos.groupby(['dt', 'band', 'mode_clean']).size().reset_index(name='count')


def create_band_activity_charts(qso_db, output_dir, contest_id, contest_start, duration_hours):
    interval_counts = _build_interval_data(qso_db)
    start_dt = pd.Timestamp(contest_start)
    end_dt = start_dt + pd.Timedelta(hours=duration_hours)

    for band in ['160m', '80m', '40m', '20m', '15m', '10m']:
        band_data = interval_counts[interval_counts['band'] == band]
        if band_data.empty:
            print(f"No data for {band}")
            continue

        pivot = band_data.pivot_table(index='dt', columns='mode_clean', values='count', fill_value=0)
        plt.figure(figsize=(12, 6))

        if 'CW' in pivot.columns and 'PH' in pivot.columns:
            plt.fill_between(pivot.index, 0, pivot['CW'], alpha=0.7, color='#1f77b4', label='CW')
            plt.fill_between(pivot.index, pivot['CW'], pivot['CW'] + pivot['PH'],
                             alpha=0.7, color='#ff7f0e', label='PH')
        elif 'CW' in pivot.columns:
            plt.fill_between(pivot.index, 0, pivot['CW'], alpha=0.7, color='#1f77b4', label='CW')
        elif 'PH' in pivot.columns:
            plt.fill_between(pivot.index, 0, pivot['PH'], alpha=0.7, color='#ff7f0e', label='PH')

        plt.title(f'{band} Band Activity Over Time', fontsize=16)
        plt.xlabel('Time (UTC)', fontsize=12)
        plt.ylabel('QSOs per 15 min', fontsize=12)
        plt.xlim(start_dt, end_dt)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=45)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(output_dir / f'{contest_id}_{band}_Activity.png', dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Created {band} activity chart")


def create_stacked_band_charts(qso_db, output_dir, contest_id, contest_start, duration_hours):
    interval_counts = _build_interval_data(qso_db)
    interval_counts = interval_counts[~interval_counts['band'].isin(['VHF+', 'Unknown'])]

    start_dt = pd.Timestamp(contest_start)
    end_dt = start_dt + pd.Timedelta(hours=duration_hours)

    bands = ['160m', '80m', '40m', '20m', '15m', '10m']
    colors = ['#8B4513', '#FF6347', '#32CD32', '#1E90FF', '#FFD700', '#FF69B4']

    for mode in ['CW', 'PH']:
        mode_data = interval_counts[interval_counts['mode_clean'] == mode]
        if mode_data.empty:
            print(f"No data for {mode} mode")
            continue

        pivot = mode_data.pivot_table(index='dt', columns='band', values='count', fill_value=0)
        for band in bands:
            if band not in pivot.columns:
                pivot[band] = 0
        pivot = pivot[bands]

        plt.figure(figsize=(12, 8))
        plt.stackplot(pivot.index, *[pivot[b] for b in bands], labels=bands, colors=colors, alpha=0.8)
        plt.title(f'All Bands Activity Over Time - {mode} Mode', fontsize=16)
        plt.xlabel('Time (UTC)', fontsize=12)
        plt.ylabel('QSOs per 15 min', fontsize=12)
        plt.xlim(start_dt, end_dt)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=45)
        plt.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / f'{contest_id}_AllBands_{mode}_Activity.png', dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Created stacked {mode} band activity chart")


def main():
    parser = argparse.ArgumentParser(description='Generate contest analysis charts')
    parser.add_argument('--meta-db', required=True, help='Path to contest_meta.db')
    parser.add_argument('--qso-db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output-dir', required=True, help='Directory for output PNG files')
    parser.add_argument('--contest-id', required=True, help='Contest ID prefix for filenames (e.g. NYQP_2025)')
    parser.add_argument('--contest-start', required=True, help='Contest start datetime UTC (e.g. "2025-10-18 14:00:00")')
    parser.add_argument('--duration-hours', type=int, default=12, help='Contest duration in hours')
    parser.add_argument('--host-state', default='NY', help='Host state/province abbreviation (e.g. NY, BC)')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Creating score box plot...")
    create_score_boxplot(args.meta_db, args.qso_db, output_dir, args.contest_id)

    print("Creating QSO distribution chart...")
    create_qso_distribution(args.meta_db, args.qso_db, output_dir, args.contest_id, args.host_state)

    print("Creating QSO histogram...")
    create_qso_histogram(args.qso_db, output_dir, args.contest_id)

    print("Creating per-band activity charts...")
    create_band_activity_charts(args.qso_db, output_dir, args.contest_id,
                                args.contest_start, args.duration_hours)

    print("Creating stacked band activity charts...")
    create_stacked_band_charts(args.qso_db, output_dir, args.contest_id,
                               args.contest_start, args.duration_hours)

    print("Done!")
    os._exit(0)   # bypass C-level teardown that segfaults on headless matplotlib


if __name__ == '__main__':
    main()
