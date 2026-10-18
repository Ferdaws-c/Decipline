"""Keep user data beside the app, including the older single-file release."""

from pathlib import Path
import os
import sys


def data_path(filename):
    override = os.environ.get("DECIPLINE_DATA_DIR")
    if override:
        return str(Path(override).resolve() / filename)
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
        candidates = (base, base.parent)
    else:
        base = Path(__file__).resolve().parent.parent
        candidates = (base, base / "dist")
    # Prefer a schedule library, then a directory containing other user data.
    for names in (("schedules.json",), ("settings.json", "stats.json")):
        for directory in candidates:
            if any((directory / name).is_file() for name in names):
                return str(directory / filename)
    return str(base / filename)
