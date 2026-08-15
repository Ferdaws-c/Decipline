# scheduler.py -- Excel schedule importer, renderer, postpone, and weekly loader.
import os
import re
from datetime import datetime, timedelta

import pandas as pd
from tkinter import filedialog

# -- Column detection ---------------------------------------------------------

_COL_ALIASES = {
    "time":     ["time", "start", "start time", "from", "hour"],
    "task":     ["task", "activity", "subject", "description", "event", "name"],
    "duration": ["duration", "dur", "length", "mins", "minutes", "hours"],
    "notes":    ["notes", "note", "details", "comment", "comments"],
}

_WEEKLY_DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]
_WEEKLY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _match_columns(df):
    mapping = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}
    for canonical, aliases in _COL_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols:
                mapping[canonical] = lower_cols[alias]
                break
    return mapping


def _clean_df(df):
    df = df.dropna(how="all").reset_index(drop=True)
    df = df.fillna("")
    return df


# -- Daily loading ------------------------------------------------------------

def load_schedule(filepath=None):
    if filepath is None:
        filepath = filedialog.askopenfilename(
            title="Open Daily Schedule",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
    if not filepath or not os.path.exists(filepath):
        return pd.DataFrame(), {}
    try:
        df      = pd.read_excel(filepath, engine="openpyxl")
        df      = _clean_df(df)
        col_map = _match_columns(df)
        return df, col_map
    except Exception as e:
        print("[scheduler] load error:", e)
        return pd.DataFrame(), {}


def get_display_rows(df, col_map):
    rows = []
    for _, row in df.iterrows():
        entry = {
            "time":     str(row.get(col_map.get("time",     ""), "")).strip(),
            "task":     str(row.get(col_map.get("task",     ""), "")).strip(),
            "duration": str(row.get(col_map.get("duration", ""), "")).strip(),
            "notes":    str(row.get(col_map.get("notes",    ""), "")).strip(),
        }
        if not entry["task"] and len(df.columns) > 0:
            entry["task"] = str(row.iloc[0]).strip()
        rows.append(entry)
    return rows


# -- Weekly loading -----------------------------------------------------------

def load_weekly_schedule(filepath=None):
    """
    Load an Excel file with 7 sheets (Monday..Sunday or Mon..Sun).
    Returns: dict { day_name: list[dict] } for each sheet found.
    """
    if filepath is None:
        filepath = filedialog.askopenfilename(
            title="Open Weekly Schedule",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
    if not filepath or not os.path.exists(filepath):
        return {}

    try:
        xl      = pd.ExcelFile(filepath, engine="openpyxl")
        sheets  = xl.sheet_names
        result  = {}

        for sheet in sheets:
            # Match to a day name (full or short)
            day = None
            su  = sheet.strip()
            for full, short in zip(_WEEKLY_DAYS, _WEEKLY_SHORT):
                if su.lower() in (full.lower(), short.lower()):
                    day = full
                    break
            if day is None:
                continue
            df      = xl.parse(sheet)
            df      = _clean_df(df)
            col_map = _match_columns(df)
            rows    = get_display_rows(df, col_map)
            result[day] = rows

        return result
    except Exception as e:
        print("[scheduler] weekly load error:", e)
        return {}


# -- Time helpers -------------------------------------------------------------

def parse_task_time(time_str):
    """'08:00' -> time object or None."""
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(time_str.strip(), fmt).time()
        except (ValueError, AttributeError):
            pass
    return None


def parse_duration_minutes(dur_str):
    """'25 min' / '1 hr' / '1.5 hr' / '30' -> int minutes."""
    if not dur_str:
        return 0
    s = dur_str.strip().lower()
    m = re.search(r"([\d.]+)\s*h", s)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.search(r"([\d.]+)\s*m", s)
    if m:
        return int(float(m.group(1)))
    m = re.match(r"^[\d.]+$", s)
    if m:
        return int(float(s))
    return 0


# -- Postpone -----------------------------------------------------------------

def postpone_rows(rows, minutes):
    """
    Shift every task's time by `minutes` (can be negative).
    Returns a new list of row dicts with updated 'time' values.
    """
    shifted = []
    for row in rows:
        t = parse_task_time(row.get("time", ""))
        if t is not None:
            dt_new  = datetime.combine(datetime.today(), t) + timedelta(minutes=minutes)
            new_row = dict(row)
            new_row["time"] = dt_new.strftime("%H:%M")
        else:
            new_row = dict(row)
        shifted.append(new_row)
    return shifted
