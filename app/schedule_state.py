# schedule_state.py -- Tracks timer sessions and computes task completion.
from datetime import datetime, timedelta


def _parse_time(time_str):
    """Parse 'HH:MM' or 'H:MM' into a datetime for today, or None."""
    if not time_str:
        return None
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            t = datetime.strptime(time_str.strip(), fmt)
            return datetime.combine(datetime.now().date(), t.time())
        except ValueError:
            pass
    return None


def _parse_duration_minutes(dur_str):
    """Parse '25 min', '1 hr', '1 hour', '90', '1.5 hr' -> int minutes, or 0."""
    if not dur_str:
        return 0
    import re
    s = dur_str.strip().lower()
    # hours
    m = re.search(r"([\d.]+)\s*h", s)
    if m:
        return int(float(m.group(1)) * 60)
    # minutes
    m = re.search(r"([\d.]+)\s*m", s)
    if m:
        return int(float(m.group(1)))
    # bare number -> assume minutes
    m = re.match(r"^[\d.]+$", s)
    if m:
        return int(float(s))
    return 0


class ScheduleTracker:
    """
    Records timer sessions and checks which scheduled tasks
    had at least `min_minutes` of active timer coverage.
    """

    def __init__(self):
        self._sessions = []          # list of (start_dt, end_dt)
        self._session_start = None

    # -- Session control ------------------------------------------------------

    def start_session(self):
        if self._session_start is None:
            self._session_start = datetime.now()

    def end_session(self):
        if self._session_start is not None:
            self._sessions.append((self._session_start, datetime.now()))
            self._session_start = None

    def reset_all(self):
        self.end_session()
        self._sessions.clear()

    # -- Completion query -----------------------------------------------------

    def get_completed_indices(self, rows, min_minutes=10):
        """
        Return a set of row indices where the timer was active
        during that task's scheduled window for >= min_minutes total.
        """
        completed = set()
        today = datetime.now().date()

        # Include current open session in computation
        sessions = list(self._sessions)
        if self._session_start is not None:
            sessions.append((self._session_start, datetime.now()))

        for i, row in enumerate(rows):
            task_start_dt = _parse_time(row.get("time", ""))
            dur_mins = _parse_duration_minutes(row.get("duration", ""))
            if task_start_dt is None or dur_mins <= 0:
                continue
            task_end_dt = task_start_dt + timedelta(minutes=dur_mins)

            total_overlap = 0.0
            for sess_start, sess_end in sessions:
                ov_start = max(task_start_dt, sess_start)
                ov_end   = min(task_end_dt,   sess_end)
                if ov_end > ov_start:
                    total_overlap += (ov_end - ov_start).total_seconds()

            if total_overlap >= min_minutes * 60:
                completed.add(i)

        return completed
