# qso-party-tools

A contest-agnostic analysis toolkit for amateur radio QSO Party contests.
Processes Cabrillo log files and generates interactive maps, animations,
statistical charts, and activity summaries.

## Supported Contests

| Contest | Config |
|---------|--------|
| NY QSO Party 2025 | `config/nyqp_2025.json` |
| BC QSO Party 2026 | `config/bcqp_2026.json` |

## Repo Layout

The repo is a **toolbox only** — no contest data lives here.

```
config/       - Contest config templates (one per contest/year)
lib/          - Shared Python libraries
scripts/      - Pipeline scripts
reference/    - GeoJSON boundary files (counties, states, provinces)
```

## Workflow

### 1. Set up a contest working directory

```
~/QSOPARTY/
  NYQP2025/
    contest.json    ← copy from config/nyqp_2025.json and rename
    logs/           ← put Cabrillo .log files here
```

```bash
mkdir -p ~/QSOPARTY/NYQP2025/logs
cp ~/dev/qso-party-tools/config/nyqp_2025.json ~/QSOPARTY/NYQP2025/contest.json
# copy .log files into ~/QSOPARTY/NYQP2025/logs/
```

### 2. Run the pipeline

```bash
cd ~/QSOPARTY/NYQP2025
python3 ~/dev/qso-party-tools/scripts/process_contest.py
```

The pipeline creates everything in the working directory:

```
NYQP2025/
  contest.json
  logs/           - your Cabrillo files (input)
  data/           - SQLite databases (created automatically)
  outputs/
    html/         - interactive maps, animations, stats pages
    charts/       - PNG charts and thumbnails
    stats/        - QC reports and JSON data files
```

### 3. Optional: shell alias

Add to `~/.bashrc` to avoid typing the full path each time:

```bash
alias process_contest="python3 ~/dev/qso-party-tools/scripts/process_contest.py"
```

Then just:

```bash
cd ~/QSOPARTY/NYQP2025
process_contest
```

### Config lookup order

If no argument is given, the script looks for `contest.json` in the current
directory. You can also pass a contest ID or explicit path:

```bash
process_contest                        # uses ./contest.json
process_contest nyqp_2025              # uses repo config/nyqp_2025.json
process_contest /path/to/myconfig.json # explicit path
```

## Adding a New Contest

1. Copy an existing config as a starting point:
   ```bash
   cp config/nyqp_2025.json config/newcontest_2026.json
   ```
2. Edit the new config (contest name, dates, boundaries, region term, etc.)
3. Add the appropriate GeoJSON boundaries file to `reference/` if needed
4. Create a working directory and run as above

## Requirements

```bash
pip install pandas matplotlib pillow wordcloud shapely fiona
```
