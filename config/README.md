# Contest Configuration Files

One JSON file per contest/year. Filename convention: `{abbreviation_lowercase}_{year}.json`

## Adding a New Contest

Copy an existing config and update the fields. Key fields:
- `contest_id` — unique identifier, used for output directory naming
- `host_state` — two-letter state abbreviation
- `schedule` — contest start/end times in UTC
- `rules` — contest-specific rules flags
- `counties_count` — number of counties in the host state
