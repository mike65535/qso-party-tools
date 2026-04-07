"""
Shared database utilities for contest analysis scripts.
"""


def window_filter_sql(contest_start_iso, contest_end_iso):
    """Return a SQL WHERE fragment and params tuple for the contest window.

    Accepts ISO timestamps with T separator (as passed from config/CLI args).
    The DB stores datetimes with a space separator, so T is converted here.

    Usage:
        clause, params = window_filter_sql(start, end)
        cursor.execute(f"SELECT ... FROM valid_qsos WHERE {clause}", params)
    """
    start_db = contest_start_iso.replace('T', ' ')
    end_db   = contest_end_iso.replace('T', ' ')
    return "datetime >= ? AND datetime <= ?", (start_db, end_db)
