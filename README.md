# qso-party-tools

A contest-agnostic analysis toolkit for state QSO Party amateur radio contests.
Processes Cabrillo log files and generates interactive maps, statistical charts, and activity summaries.

## Supported Contests

| Contest | Config |
|---------|--------|
| NY QSO Party 2025 | `config/nyqp_2025.json` |

## Usage

```bash
# 1. Build databases from log files
python3 scripts/create_sql_db.py <logs_dir> <output_dir>

# 2. Run full pipeline for a contest
python3 scripts/process_contest.py config/nyqp_2025.json
```

## Project Structure

```
config/     - One JSON config file per contest/year
lib/        - Shared library components
scripts/    - Analysis and generation scripts
data/       - Contest log files and databases (gitignored)
outputs/    - Generated HTML, charts, maps (gitignored)
```

## Requirements

```bash
pip install pandas matplotlib pillow
```
