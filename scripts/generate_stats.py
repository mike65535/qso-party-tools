#!/usr/bin/env python3
"""
Generate contest statistics HTML and JSON summary.
"""

import sqlite3
import json
import argparse
from datetime import datetime
from pathlib import Path

US_STATE_NAMES = {
    'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California',
    'CO':'Colorado','CT':'Connecticut','DE':'Delaware','DC':'Dist. of Columbia',
    'FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana',
    'IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine',
    'MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota',
    'MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada',
    'NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York',
    'NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma',
    'OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina',
    'SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont',
    'VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin',
    'WY':'Wyoming',
}

CA_PROVINCE_NAMES = {
    'AB':'Alberta','BC':'British Columbia','MB':'Manitoba','NB':'New Brunswick',
    'NL':'Newfoundland & Labrador','NS':'Nova Scotia','NT':'Northwest Territories',
    'NU':'Nunavut','ON':'Ontario','PE':'Prince Edward Island','QC':'Quebec',
    'SK':'Saskatchewan','YT':'Yukon',
}

# NY county abbreviations — used to group county-level QSOs under state 'NY'
NY_COUNTIES = {
    'ALB','ALL','BRM','BRX','CAT','CAY','CHA','CHE','CGO','CLI',
    'COL','COR','DEL','DUT','ERI','ESS','FRA','FUL','GEN','GRE',
    'HAM','HER','JEF','KIN','LEW','LIV','MAD','MON','MTG','NAS',
    'NEW','NIA','ONE','ONO','ONT','ORA','ORL','OSW','OTS','PUT',
    'QUE','REN','RIC','ROC','SAR','SCH','SCO','SCU','SEN','STE',
    'STL','SUF','SUL','TIO','TOM','ULS','WAR','WAS','WAY','WES',
    'WYO','YAT',
}

NY_COUNTY_NAMES = {
    "ALB": "Albany",    "ALL": "Allegany",  "BRX": "Bronx",      "BRM": "Broome",
    "CAT": "Cattaraugus","CAY": "Cayuga",   "CHA": "Chautauqua", "CHE": "Chemung",
    "CGO": "Chenango",  "CLI": "Clinton",   "COL": "Columbia",   "COR": "Cortland",
    "DEL": "Delaware",  "DUT": "Dutchess",  "ERI": "Erie",       "ESS": "Essex",
    "FRA": "Franklin",  "FUL": "Fulton",    "GEN": "Genesee",    "GRE": "Greene",
    "HAM": "Hamilton",  "HER": "Herkimer",  "JEF": "Jefferson",  "KIN": "Kings",
    "LEW": "Lewis",     "LIV": "Livingston","MAD": "Madison",    "MON": "Monroe",
    "MTG": "Montgomery","NAS": "Nassau",    "NEW": "New York",   "NIA": "Niagara",
    "ONE": "Oneida",    "ONO": "Onondaga",  "ONT": "Ontario",    "ORA": "Orange",
    "ORL": "Orleans",   "OSW": "Oswego",    "OTS": "Otsego",     "PUT": "Putnam",
    "QUE": "Queens",    "REN": "Rensselaer","RIC": "Richmond",   "ROC": "Rockland",
    "SAR": "Saratoga",  "SCH": "Schenectady","SCO": "Schoharie", "SCU": "Schuyler",
    "SEN": "Seneca",    "STL": "St. Lawrence","STE": "Steuben",  "SUF": "Suffolk",
    "SUL": "Sullivan",  "TIO": "Tioga",     "TOM": "Tompkins",   "ULS": "Ulster",
    "WAR": "Warren",    "WAS": "Washington","WAY": "Wayne",      "WES": "Westchester",
    "WYO": "Wyoming",   "YAT": "Yates",
}


def _mode_case(col):
    """SQL CASE expression mapping raw mode values to CW/PH/DIG."""
    return (
        f"SUM(CASE WHEN {col}='CW' THEN 1 ELSE 0 END),"
        f"SUM(CASE WHEN {col} IN ('PH','FM','SSB','AM') THEN 1 ELSE 0 END),"
        f"SUM(CASE WHEN {col} IN ('DG','RY','DIG','FT8','FT4','PSK','RTTY') THEN 1 ELSE 0 END)"
    )


def generate_county_breakdown(qso_db, host_counties=None, contest_start=None, contest_end=None):
    """Return per-county sent/received counts by mode for host-state counties."""
    counties = host_counties or NY_COUNTIES
    placeholders = ','.join(f"'{c}'" for c in counties)
    win = f"AND datetime >= '{contest_start}' AND datetime <= '{contest_end}'" if contest_start else ""

    conn = sqlite3.connect(qso_db)
    sent_sql = f"""
        SELECT tx_county,
            {_mode_case('mode')},
            COUNT(*)
        FROM valid_qsos WHERE tx_county IN ({placeholders}) {win}
        GROUP BY tx_county
    """
    rcvd_sql = f"""
        SELECT rx_county,
            {_mode_case('mode')},
            COUNT(*)
        FROM valid_qsos WHERE rx_county IN ({placeholders}) {win}
        GROUP BY rx_county
    """

    sent = {r[0]: {'cw': r[1], 'ph': r[2], 'dig': r[3], 'total': r[4]}
            for r in conn.execute(sent_sql)}
    rcvd = {r[0]: {'cw': r[1], 'ph': r[2], 'dig': r[3], 'total': r[4]}
            for r in conn.execute(rcvd_sql)}
    conn.close()

    result = {}
    for county in sorted(counties):
        result[county] = {
            'sent': sent.get(county, {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}),
            'rcvd': rcvd.get(county, {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}),
        }
    return result


def generate_state_breakdown(qso_db, host_counties=None, host_state='NY', contest_start=None, contest_end=None):
    """Return per-state sent/received counts by mode."""
    counties = host_counties or NY_COUNTIES
    placeholders = ','.join(f"'{c}'" for c in counties)
    win = f"AND datetime >= '{contest_start}' AND datetime <= '{contest_end}'" if contest_start else ""

    conn = sqlite3.connect(qso_db)
    sent_sql = f"""
        SELECT
            CASE WHEN UPPER(tx_county) IN ({placeholders}) THEN '{host_state}'
                 ELSE UPPER(tx_county) END as state,
            {_mode_case('mode')},
            COUNT(*)
        FROM valid_qsos WHERE tx_county IS NOT NULL AND tx_county != '' {win}
        GROUP BY state
    """
    rcvd_sql = f"""
        SELECT
            CASE WHEN UPPER(rx_county) IN ({placeholders}) THEN '{host_state}'
                 ELSE UPPER(rx_county) END as state,
            {_mode_case('mode')},
            COUNT(*)
        FROM valid_qsos WHERE rx_county IS NOT NULL AND rx_county != '' {win}
        GROUP BY state
    """

    sent = {r[0]: {'cw': r[1], 'ph': r[2], 'dig': r[3], 'total': r[4]}
            for r in conn.execute(sent_sql)}
    rcvd = {r[0]: {'cw': r[1], 'ph': r[2], 'dig': r[3], 'total': r[4]}
            for r in conn.execute(rcvd_sql)}
    conn.close()

    zero = {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}

    # Seed with every known US state and Canadian province/territory so that
    # locations with 0 QSOs still get a row in the output.
    all_states = (
        {s: 'US'     for s in US_STATE_NAMES} |
        {s: 'Canada' for s in CA_PROVINCE_NAMES}
    )
    # Add any codes that appeared in the DB but aren't in the known sets
    for s in set(sent) | set(rcvd):
        if s not in all_states:
            if s == 'DX':
                all_states[s] = 'DX'
            else:
                all_states[s] = 'unrecognized'

    result = {}
    for state, group in all_states.items():
        result[state] = {
            'sent':  sent.get(state, zero.copy()),
            'rcvd':  rcvd.get(state, zero.copy()),
            'group': group,
        }
    return result


def generate_contest_stats(meta_db, qso_db, contest_start, contest_end):
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

    start_db = contest_start.replace('T', ' ')
    end_db   = contest_end.replace('T', ' ')

    qso_conn = sqlite3.connect(qso_db)
    stats['total_qsos'] = qso_conn.execute(
        "SELECT COUNT(*) FROM valid_qsos WHERE datetime >= ? AND datetime <= ?",
        (start_db, end_db)
    ).fetchone()[0]
    if ny_callsigns:
        placeholders = ','.join('?' * len(ny_callsigns))
        stats['qsos_by_ny'] = qso_conn.execute(
            f"SELECT COUNT(*) FROM valid_qsos WHERE datetime >= ? AND datetime <= ? "
            f"AND station_call IN ({placeholders})",
            (start_db, end_db, *ny_callsigns)
        ).fetchone()[0]
    else:
        stats['qsos_by_ny'] = 0

    # Filtered QSOs for audit — structural failures + out-of-window
    rows = qso_conn.execute("""
        SELECT id, log_file, station_call, datetime, freq, mode,
               tx_call, tx_county, rx_call, rx_county
        FROM qsos
        WHERE id NOT IN (SELECT id FROM valid_qsos)
           OR datetime < ? OR datetime > ?
        ORDER BY log_file, datetime
    """, (start_db, end_db)).fetchall()
    stats['filtered_qsos'] = [
        {
            'id': r[0], 'log_file': r[1], 'station_call': r[2],
            'datetime': r[3], 'freq': r[4], 'mode': r[5],
            'tx_call': r[6], 'tx_county': r[7],
            'rx_call': r[8], 'rx_county': r[9],
            'reason': _filter_reason(r[7], r[9], r[3], start_db, end_db),
        }
        for r in rows
    ]
    qso_conn.close()

    return stats


def _filter_reason(tx_county, rx_county, dt_str=None, start_db=None, end_db=None):
    """Human-readable reason why a QSO was excluded."""
    reasons = []
    if dt_str and start_db and end_db:
        if dt_str < start_db or dt_str > end_db:
            reasons.append(f"outside contest window ({dt_str.strip()} not in {start_db}–{end_db})")
    for label, val in [('tx_county', tx_county or ''), ('rx_county', rx_county or '')]:
        if '/' in val:
            reasons.append(f"{label} is county-line slash format ({val!r})")
        elif len(val) < 2 or len(val) > 3:
            reasons.append(f"{label} has unexpected length ({val!r})")
    return '; '.join(reasons) if reasons else 'unknown'


def _mode_breakdown_table(title, rows_data, label_col, label_fn=None):
    """Render a sent/received by mode HTML table.

    rows_data: dict of label → {'sent': {cw,ph,dig,total}, 'rcvd': {cw,ph,dig,total}}
    label_fn: optional callable to format the row label
    """
    table_css = """
    <style>
      .breakdown-table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
      .breakdown-table th, .breakdown-table td { border: 1px solid #ccc; padding: 4px 8px; text-align: right; }
      .breakdown-table th { background: #2c3e50; color: white; text-align: center; }
      .breakdown-table th.label-col { text-align: left; }
      .breakdown-table td.label-col { text-align: left; font-weight: bold; }
      .breakdown-table tr:nth-child(even) { background: #f5f5f5; }
      .breakdown-table td.total { font-weight: bold; background: #eaf0fb; }
      .breakdown-table tfoot td { font-weight: bold; background: #dce8f7; }
      .breakdown-group { display: inline-block; width: 100%; overflow-x: auto; }
    </style>"""

    hdr = (
        f'<div class="breakdown-group">'
        f'<h3>{title}</h3>'
        f'<table class="breakdown-table">'
        f'<thead><tr>'
        f'<th class="label-col">{label_col}</th>'
        f'<th>CW Sent</th><th>CW Rcvd</th>'
        f'<th>PH Sent</th><th>PH Rcvd</th>'
        f'<th>DIG Sent</th><th>DIG Rcvd</th>'
        f'<th class="total">Total Sent</th><th class="total">Total Rcvd</th>'
        f'</tr></thead><tbody>'
    )

    body = ''
    tot_s = {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}
    tot_r = {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}
    for label, d in rows_data.items():
        s, r = d['sent'], d['rcvd']
        display = label_fn(label) if label_fn else label
        body += (
            f'<tr>'
            f'<td class="label-col">{display}</td>'
            f'<td>{s["cw"]:,}</td><td>{r["cw"]:,}</td>'
            f'<td>{s["ph"]:,}</td><td>{r["ph"]:,}</td>'
            f'<td>{s["dig"]:,}</td><td>{r["dig"]:,}</td>'
            f'<td class="total">{s["total"]:,}</td><td class="total">{r["total"]:,}</td>'
            f'</tr>'
        )
        for k in tot_s:
            tot_s[k] += s[k]
            tot_r[k] += r[k]

    footer = (
        f'</tbody><tfoot><tr>'
        f'<td class="label-col">TOTAL</td>'
        f'<td>{tot_s["cw"]:,}</td><td>{tot_r["cw"]:,}</td>'
        f'<td>{tot_s["ph"]:,}</td><td>{tot_r["ph"]:,}</td>'
        f'<td>{tot_s["dig"]:,}</td><td>{tot_r["dig"]:,}</td>'
        f'<td class="total">{tot_s["total"]:,}</td><td class="total">{tot_r["total"]:,}</td>'
        f'</tr></tfoot></table></div>'
    )
    return table_css + hdr + body + footer


def _grouped_state_table(state_breakdown):
    """Render state breakdown as three grouped sections: US States, Canada, DX."""

    def _rows_for_group(group, name_lookup):
        return {
            code: data for code, data in state_breakdown.items()
            if data['group'] == group
        }

    def _section(group_label, rows, name_lookup):
        if not rows:
            return ''
        cols = (
            '<th class="label-col">State / Province</th>'
            '<th>CW Sent</th><th>CW Rcvd</th>'
            '<th>PH Sent</th><th>PH Rcvd</th>'
            '<th>DIG Sent</th><th>DIG Rcvd</th>'
            '<th class="total">Total Sent</th><th class="total">Total Rcvd</th>'
        )
        body = ''
        tot_s = {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}
        tot_r = {'cw': 0, 'ph': 0, 'dig': 0, 'total': 0}
        for code in sorted(rows, key=lambda c: name_lookup.get(c, c)):
            d = rows[code]
            s, r = d['sent'], d['rcvd']
            name = name_lookup.get(code, code)
            label = f"{name} ({code})" if name != code else code
            body += (
                f'<tr>'
                f'<td class="label-col">{label}</td>'
                f'<td>{s["cw"]:,}</td><td>{r["cw"]:,}</td>'
                f'<td>{s["ph"]:,}</td><td>{r["ph"]:,}</td>'
                f'<td>{s["dig"]:,}</td><td>{r["dig"]:,}</td>'
                f'<td class="total">{s["total"]:,}</td>'
                f'<td class="total">{r["total"]:,}</td>'
                f'</tr>'
            )
            for k in tot_s:
                tot_s[k] += s[k]
                tot_r[k] += r[k]
        footer = (
            f'<tr class="group-total">'
            f'<td class="label-col">{group_label} Total</td>'
            f'<td>{tot_s["cw"]:,}</td><td>{tot_r["cw"]:,}</td>'
            f'<td>{tot_s["ph"]:,}</td><td>{tot_r["ph"]:,}</td>'
            f'<td>{tot_s["dig"]:,}</td><td>{tot_r["dig"]:,}</td>'
            f'<td class="total">{tot_s["total"]:,}</td>'
            f'<td class="total">{tot_r["total"]:,}</td>'
            f'</tr>'
        )
        return (
            f'<tr class="group-header"><th colspan="9">{group_label}</th></tr>'
            f'<tr>{cols}</tr>'
            f'{body}{footer}'
        )

    css = """
    <style>
      .state-table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
      .state-table th, .state-table td { border: 1px solid #ccc; padding: 4px 8px; text-align: right; }
      .state-table th.label-col, .state-table td.label-col { text-align: left; }
      .state-table tr:nth-child(even) { background: #f5f5f5; }
      .state-table td.total { font-weight: bold; background: #eaf0fb; }
      .state-table tr.group-header th { background: #2c3e50; color: white; text-align: left;
                                        font-size: 1em; padding: 6px 8px; }
      .state-table tr.group-total td { font-weight: bold; background: #dce8f7; }
    </style>"""

    us_rows   = _rows_for_group('US', US_STATE_NAMES)
    ca_rows   = _rows_for_group('Canada', CA_PROVINCE_NAMES)
    dx_rows   = _rows_for_group('DX', {})
    unk_rows  = _rows_for_group('unrecognized', {})

    unk_note = ''
    if unk_rows:
        codes = ', '.join(f'<b>{c}</b>' for c in sorted(unk_rows))
        unk_note = (
            f'<p style="color:#7b241c;font-size:0.85em;margin-top:0.5em;">'
            f'Non-compliant exchange codes (not counted above): {codes} — see errata.</p>'
        )

    html = (
        f'{css}<div class="stat-section"><h3>QSOs by State / Province / DX</h3>'
        f'<div style="overflow-x:auto"><table class="state-table"><tbody>'
        f'{_section("US States", us_rows, US_STATE_NAMES)}'
        f'{_section("Canadian Provinces & Territories", ca_rows, CA_PROVINCE_NAMES)}'
        f'{_section("DX", dx_rows, {})}'
        f'</tbody></table></div>'
        f'{unk_note}</div>'
    )
    return html


def format_stats_html(stats, contest_name):
    """Format stats as an HTML fragment."""

    def section(title, items):
        rows = ''.join(f"<li><strong>{k}:</strong> {v:,}</li>\n" for k, v in items.items())
        return f'<div class="stat-section"><h3>{title}</h3><ul>\n{rows}</ul></div>\n'

    now = datetime.now().astimezone()
    generated = now.strftime('%Y-%m-%d %H:%M ') + now.strftime('%Z')

    html = f'<div class="contest-stats">\n<h2>{contest_name} Statistics</h2>\n'
    html += f'<p style="color:#666;font-size:0.85em;margin-top:-0.5em;">Generated {generated}</p>\n'

    html += section("Participation", {
        "Total Logs Submitted": stats['total_logs'],
        "Unique Callsigns": stats['unique_callsigns'],
        "Host-State Stations": stats['ny_stations'],
        "Non-Host-State Stations": stats['non_ny_stations'],
    })

    html += section("QSO Activity", {
        "Total QSO Records": stats['total_qsos'],
        "QSO Records by Host-State Stations": stats['qsos_by_ny'],
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

    if stats.get('county_breakdown'):
        def county_label(abbrev):
            name = NY_COUNTY_NAMES.get(abbrev, abbrev)
            return f"{abbrev} – {name}"
        html += _mode_breakdown_table(
            "QSOs by Host-State County", stats['county_breakdown'],
            label_col="County", label_fn=county_label
        )

    if stats.get('state_breakdown'):
        html += _grouped_state_table(stats['state_breakdown'])

    html += '</div>'
    return html


def _filtered_qsos_table(filtered_qsos):
    """Render a table of QSOs excluded by the valid_qsos filter for human audit."""
    count = len(filtered_qsos)
    heading = f"Filtered QSOs — Data Quality Audit ({count} excluded)"

    css = """
    <style>
      .audit-table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.85em; }
      .audit-table th { background: #7b241c; color: white; padding: 4px 8px; text-align: left; }
      .audit-table td { border: 1px solid #ccc; padding: 3px 7px; vertical-align: top; }
      .audit-table tr:nth-child(even) { background: #fdf2f2; }
      .audit-table td.reason { color: #7b241c; font-style: italic; }
    </style>"""

    if count == 0:
        return f'{css}<div class="stat-section"><h3>{heading}</h3><p>None — all QSOs passed validation.</p></div>\n'

    hdr = (
        f'<div class="stat-section"><h3>{heading}</h3>'
        f'<table class="audit-table"><thead><tr>'
        f'<th>Log File</th><th>Station</th><th>Datetime</th>'
        f'<th>Freq</th><th>Mode</th>'
        f'<th>Tx Call</th><th>Tx County</th>'
        f'<th>Rx Call</th><th>Rx County</th>'
        f'<th>Reason</th>'
        f'</tr></thead><tbody>'
    )

    body = ''
    for q in filtered_qsos:
        body += (
            f'<tr>'
            f'<td>{q["log_file"]}</td>'
            f'<td>{q["station_call"]}</td>'
            f'<td>{q["datetime"]}</td>'
            f'<td>{q["freq"]}</td>'
            f'<td>{q["mode"]}</td>'
            f'<td>{q["tx_call"]}</td>'
            f'<td><b>{q["tx_county"]}</b></td>'
            f'<td>{q["rx_call"]}</td>'
            f'<td><b>{q["rx_county"]}</b></td>'
            f'<td class="reason">{q["reason"]}</td>'
            f'</tr>'
        )

    return css + hdr + body + '</tbody></table></div>\n'


def build_mobile_discrepancies(meta_db, qso_db, mobiles_json, min_counties=2, min_qsos=10):
    """Return list of stations that declared MOBILE but didn't qualify for the animation map."""
    import sqlite3 as _sq
    map_calls = set()
    if mobiles_json and Path(mobiles_json).exists():
        with open(mobiles_json) as f:
            map_calls = set(json.load(f).keys())

    meta_conn = _sq.connect(meta_db)
    declared = {r[0]: r[1] for r in meta_conn.execute(
        "SELECT callsign, location FROM stations WHERE station_type = 'MOBILE'"
    ).fetchall()}
    meta_conn.close()

    qso_conn = _sq.connect(qso_db)
    discrepancies = []
    for call, location in sorted(declared.items()):
        if call in map_calls:
            continue
        rows = qso_conn.execute(
            "SELECT DISTINCT tx_county FROM valid_qsos WHERE station_call=?", (call,)
        ).fetchall()
        counties = [r[0] for r in rows]
        n_qsos = qso_conn.execute(
            "SELECT COUNT(*) FROM valid_qsos WHERE station_call=?", (call,)
        ).fetchone()[0]
        reasons = []
        if location and location not in ('NY',):
            reasons.append(f"non-NY location ({location})")
        if len(counties) < min_counties:
            reasons.append(f"only {len(counties)} county — below min {min_counties}")
        if n_qsos < min_qsos:
            reasons.append(f"only {n_qsos} QSOs — below min {min_qsos}")
        if not reasons:
            reasons.append("unknown — not detected by mobile detector")
        discrepancies.append({
            'callsign': call,
            'location': location or '—',
            'counties': ', '.join(counties) if counties else '—',
            'n_qsos': n_qsos,
            'reason': '; '.join(reasons),
        })
    qso_conn.close()
    return discrepancies


def format_errata_html(filtered_qsos, normalizations, mobile_discrepancies, contest_name):
    """Render a standalone errata HTML page."""
    now = datetime.now().astimezone()
    generated = now.strftime('%Y-%m-%d %H:%M ') + now.strftime('%Z')

    page_css = """
    <style>
      body { font-family: Arial, sans-serif; margin: 2em; color: #222; }
      h1 { color: #2c3e50; }
      h2 { color: #7b241c; margin-top: 2em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
      p.meta { color: #666; font-size: 0.85em; margin-top: -0.5em; }
      .norm-table, .audit-table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.85em; }
      .norm-table th, .audit-table th { background: #2c3e50; color: white; padding: 4px 8px; text-align: left; }
      .norm-table td, .audit-table td { border: 1px solid #ccc; padding: 3px 7px; vertical-align: top; }
      .norm-table tr:nth-child(even), .audit-table tr:nth-child(even) { background: #f5f5f5; }
      .audit-table td.reason { color: #7b241c; font-style: italic; }
    </style>"""

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>{contest_name} — Errata</title>
{page_css}
</head><body>
<h1>{contest_name} — Errata</h1>
<p class="meta">Generated {generated}</p>
<p>This page documents automated processing decisions applied to submitted logs.
No QSO data was manually altered; entries below reflect structural normalization
and validation rules applied uniformly to all logs.</p>
"""

    # ── Callsign normalizations ───────────────────────────────────────────────
    html += f'<h2>Callsign Normalizations ({len(normalizations)})</h2>\n'
    if normalizations:
        html += (
            '<p>The following log headers contained portable/mobile suffixes '
            '(e.g. <code>/M</code>, <code>/P</code>, <code>/1</code>). '
            'The suffix was stripped for all comparisons and tallies.</p>'
            '<table class="norm-table"><thead><tr>'
            '<th>Log File</th><th>Original Callsign</th><th>Normalized To</th><th>Reason</th>'
            '</tr></thead><tbody>'
        )
        for n in sorted(normalizations, key=lambda x: x['log_file']):
            html += (
                f'<tr><td>{n["log_file"]}</td>'
                f'<td><b>{n["original"]}</b></td>'
                f'<td><b>{n["normalized"]}</b></td>'
                f'<td>{n["reason"]}</td></tr>'
            )
        html += '</tbody></table>\n'
    else:
        html += '<p>None — all log header callsigns were already in standard form.</p>\n'

    # ── Mobile discrepancies ──────────────────────────────────────────────────
    html += f'<h2>Declared Mobile — Not Shown on Animation Map ({len(mobile_discrepancies)})</h2>\n'
    if mobile_discrepancies:
        html += (
            '<p>These stations declared <code>CATEGORY-STATION: MOBILE</code> in their log header '
            'but did not qualify for the mobile animation map. Qualification requires operating '
            f'from at least {2} NY counties with at least {10} total QSOs.</p>'
            '<table class="norm-table"><thead><tr>'
            '<th>Callsign</th><th>Location</th><th>Counties Operated</th><th>QSOs</th><th>Reason</th>'
            '</tr></thead><tbody>'
        )
        for d in mobile_discrepancies:
            html += (
                f'<tr><td><b>{d["callsign"]}</b></td>'
                f'<td>{d["location"]}</td>'
                f'<td>{d["counties"]}</td>'
                f'<td>{d["n_qsos"]}</td>'
                f'<td class="reason">{d["reason"]}</td></tr>'
            )
        html += '</tbody></table>\n'
    else:
        html += '<p>None — all declared mobile stations met the animation map criteria.</p>\n'

    # ── Excluded QSOs ─────────────────────────────────────────────────────────
    count = len(filtered_qsos)
    html += f'<h2>Excluded QSOs ({count})</h2>\n'
    if filtered_qsos:
        html += (
            '<p>The following QSO records were excluded from all statistics. '
            'Common causes: county exchange contains a slash (county-line notation logged '
            'in the exchange field), exchange code too short or too long, or timestamp '
            'outside the official contest window.</p>'
            '<table class="audit-table"><thead><tr>'
            '<th>Log File</th><th>Station</th><th>Datetime</th>'
            '<th>Freq</th><th>Mode</th>'
            '<th>Tx Call</th><th>Tx County</th>'
            '<th>Rx Call</th><th>Rx County</th>'
            '<th>Reason</th>'
            '</tr></thead><tbody>'
        )
        for q in filtered_qsos:
            html += (
                f'<tr>'
                f'<td>{q["log_file"]}</td>'
                f'<td>{q["station_call"]}</td>'
                f'<td>{q["datetime"]}</td>'
                f'<td>{q["freq"]}</td>'
                f'<td>{q["mode"]}</td>'
                f'<td>{q["tx_call"]}</td>'
                f'<td><b>{q["tx_county"]}</b></td>'
                f'<td>{q["rx_call"]}</td>'
                f'<td><b>{q["rx_county"]}</b></td>'
                f'<td class="reason">{q["reason"]}</td>'
                f'</tr>'
            )
        html += '</tbody></table>\n'
    else:
        html += '<p>None — all QSO records passed validation.</p>\n'

    html += '</body></html>'
    return html


def main():
    parser = argparse.ArgumentParser(description='Generate contest statistics')
    parser.add_argument('--meta-db', required=True, help='Path to contest_meta.db')
    parser.add_argument('--qso-db', required=True, help='Path to contest_qsos.db')
    parser.add_argument('--output-dir', required=True, help='Directory for output files')
    parser.add_argument('--contest-name', required=True, help='Contest display name (e.g. "2025 New York QSO Party")')
    parser.add_argument('--contest-start', required=True, help='Contest start UTC (e.g. "2025-10-18T14:00:00")')
    parser.add_argument('--contest-end',   required=True, help='Contest end UTC (e.g. "2025-10-19T02:00:00")')
    parser.add_argument('--normalizations', default=None, help='Path to callsign_normalizations.json')
    parser.add_argument('--mobiles', default=None, help='Path to mobile_stations.json')
    args = parser.parse_args()

    contest_start = args.contest_start.replace('T', ' ')
    contest_end   = args.contest_end.replace('T', ' ')

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = generate_contest_stats(args.meta_db, args.qso_db, contest_start, contest_end)
    stats['county_breakdown'] = generate_county_breakdown(args.qso_db, contest_start=contest_start, contest_end=contest_end)
    stats['state_breakdown']  = generate_state_breakdown(args.qso_db, contest_start=contest_start, contest_end=contest_end)

    json_path = output_dir / 'contest_stats.json'
    with open(json_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Saved {json_path}")

    html_path = output_dir / 'contest_stats.html'
    with open(html_path, 'w') as f:
        f.write(format_stats_html(stats, args.contest_name))
    print(f"Saved {html_path}")

    normalizations = []
    if args.normalizations and Path(args.normalizations).exists():
        with open(args.normalizations) as f:
            normalizations = json.load(f)

    mobile_discrepancies = build_mobile_discrepancies(
        args.meta_db, args.qso_db, args.mobiles)

    errata_path = output_dir / 'errata.html'
    with open(errata_path, 'w') as f:
        f.write(format_errata_html(
            stats.get('filtered_qsos', []), normalizations,
            mobile_discrepancies, args.contest_name))
    print(f"Saved {errata_path}")

    print(f"Total Logs: {stats['total_logs']}")
    print(f"Host-State Stations: {stats['ny_stations']}")
    print(f"Non-Host-State Stations: {stats['non_ny_stations']}")
    print(f"Total QSOs: {stats['total_qsos']:,}")


if __name__ == '__main__':
    main()
