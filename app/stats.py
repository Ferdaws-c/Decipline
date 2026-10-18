"""Thread-safe study statistics, buffered and saved every 15 seconds."""

import atexit
import copy
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime
from .paths import data_path

STATS_PATH = data_path("stats.json")
SAVE_INTERVAL = 15
_lock = threading.RLock()
_stats = None
_loaded_path = None
_dirty = False
_last_save = 0.0


def _load_stats():
    """Read a snapshot, including focus time not yet flushed to disk."""
    with _lock:
        return copy.deepcopy(_get_stats())


def _get_stats():
    global _stats, _loaded_path, _dirty, _last_save
    path = os.path.abspath(STATS_PATH)
    if _stats is None or path != _loaded_path:
        data = {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            pass
        _stats = {"streak": 0, "last_active_date": None, "study_seconds": 0,
                  "break_seconds": 0, "tasks_completed": 0, "history": {}, "hourly": {},
                  "courses": {}, "lecture_sessions": {}}
        _stats.update(data)
        _loaded_path = path
        _dirty = False
        _last_save = time.monotonic()
    return _stats


def flush_stats():
    """Atomically persist pending changes; retain them if writing fails."""
    global _dirty, _last_save
    with _lock:
        if not _dirty or _stats is None:
            return True
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                    dir=os.path.dirname(_loaded_path), delete=False) as f:
                temporary = f.name
                json.dump(_stats, f, indent=2)
            os.replace(temporary, _loaded_path)
        except OSError:
            logging.getLogger(__name__).exception("Could not save study statistics")
            return False
        else:
            _dirty = False
            _last_save = time.monotonic()
            return True
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


def _record_activity(stats, now):
    today = now.strftime("%Y-%m-%d")
    last_active = stats.get("last_active_date")
    if last_active != today:
        last_date = datetime.strptime(last_active, "%Y-%m-%d").date() if last_active else None
        gap = (now.date() - last_date).days if last_date else None
        stats["streak"] = stats.get("streak", 0) + 1 if gap == 1 else 1
        stats["last_active_date"] = today
    day = stats["history"].setdefault(today, {})
    day.setdefault("study_seconds", 0)
    day.setdefault("tasks", 0)
    return today


def check_streak():
    global _dirty
    with _lock:
        stats = _get_stats()
        last_active = stats.get("last_active_date")
        if last_active and (datetime.today().date() -
                datetime.strptime(last_active, "%Y-%m-%d").date()).days > 1:
            if stats.get("streak", 0):
                stats["streak"] = 0
                _dirty = True
                flush_stats()
        return stats.get("streak", 0)


def record_activity():
    global _dirty
    with _lock:
        _record_activity(_get_stats(), datetime.now())
        _dirty = True
        flush_stats()


def add_study_time(seconds):
    global _dirty
    if seconds <= 0:
        return
    with _lock:
        stats = _get_stats()
        now = datetime.now()
        today = _record_activity(stats, now)
        stats["study_seconds"] += seconds
        stats["history"][today]["study_seconds"] += seconds
        hourly = stats["hourly"].setdefault(today, {})
        hour = str(now.hour)
        hourly[hour] = hourly.get(hour, 0) + seconds
        _dirty = True
        if time.monotonic() - _last_save >= SAVE_INTERVAL:
            flush_stats()


def add_break_time(seconds):
    """Breaks have their own counter and never affect focus, hourly study, or streaks."""
    global _dirty
    if seconds <= 0:
        return
    with _lock:
        stats = _get_stats()
        stats["break_seconds"] += seconds
        today = datetime.now().strftime("%Y-%m-%d")
        day = stats["history"].setdefault(today, {"study_seconds": 0, "tasks": 0})
        day["break_seconds"] = day.get("break_seconds", 0) + seconds
        _dirty = True
        if time.monotonic() - _last_save >= SAVE_INTERVAL:
            flush_stats()


def _edit_courses(edit):
    """Commit a metadata change atomically; leave memory and disk intact on failure."""
    global _dirty
    with _lock:
        data = _get_stats()
        previous = copy.deepcopy(data["courses"])
        was_dirty = _dirty
        try:
            result = edit(data["courses"])
            _dirty = True
            if not flush_stats():
                raise OSError("Could not save your changes. Check the data folder and try again.")
        except Exception:
            data["courses"] = previous
            _dirty = was_dirty
            raise
        return result


def _clean_name(name, kind):
    name = name.strip()
    if not name:
        raise ValueError(f"Enter a {kind} name.")
    return name


def create_course(name):
    name = _clean_name(name, "course")
    def edit(courses):
        for cid, course in courses.items():
            if course["name"].casefold() == name.casefold():
                course["deleted"] = False
                return cid
        cid = str(uuid.uuid4())
        courses[cid] = {"name": name, "lectures": {}}
        return cid
    return _edit_courses(edit)


def create_lecture(course_id, name):
    name = _clean_name(name, "lecture")
    def edit(courses):
        course = courses[course_id]
        if course.get("deleted"):
            raise ValueError("Restore this course before adding lectures.")
        lectures = course["lectures"]
        for lid, lecture in lectures.items():
            if lecture["name"].casefold() == name.casefold():
                lecture["deleted"] = False
                return lid
        lid = str(uuid.uuid4())
        lectures[lid] = {"name": name, "study_seconds": 0, "break_seconds": 0}
        return lid
    return _edit_courses(edit)


def rename_course(course_id, name):
    name = _clean_name(name, "course")
    def edit(courses):
        if any(cid != course_id and c["name"].casefold() == name.casefold() for cid, c in courses.items()):
            raise ValueError("A course with that name already exists.")
        courses[course_id]["name"] = name
    _edit_courses(edit)


def rename_lecture(course_id, lecture_id, name):
    name = _clean_name(name, "lecture")
    def edit(courses):
        lectures = courses[course_id]["lectures"]
        if any(lid != lecture_id and l["name"].casefold() == name.casefold() for lid, l in lectures.items()):
            raise ValueError("A lecture with that name already exists in this course.")
        lectures[lecture_id]["name"] = name
    _edit_courses(edit)


def _set_removed(course_id, lecture_id, removed):
    def edit(courses):
        course = courses[course_id]
        if lecture_id is None:
            course["deleted"] = removed
        else:
            if not removed and course.get("deleted"):
                raise ValueError("Restore the course before restoring its lectures.")
            course["lectures"][lecture_id]["deleted"] = removed
    _edit_courses(edit)


def delete_course(course_id):
    _set_removed(course_id, None, True)


def restore_course(course_id):
    _set_removed(course_id, None, False)


def delete_lecture(course_id, lecture_id):
    _set_removed(course_id, lecture_id, True)


def restore_lecture(course_id, lecture_id):
    _set_removed(course_id, lecture_id, False)


def get_courses(include_removed=False):
    with _lock:
        courses = copy.deepcopy(_get_stats()["courses"])
    if include_removed:
        return courses
    return {cid: {**course, "totals": course_totals(course), "lectures": {lid: lecture for lid, lecture in course.get("lectures", {}).items()
                     if not lecture.get("deleted")}}
            for cid, course in courses.items() if not course.get("deleted")}


def start_lecture_session(course_id, lecture_id):
    global _dirty
    with _lock:
        stats = _get_stats()
        lecture = stats["courses"][course_id]["lectures"][lecture_id]
        sid = str(uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        stats["lecture_sessions"][sid] = {
            "course_id": course_id, "lecture_id": lecture_id,
            "started_at": now, "last_recorded_at": now, "ended_at": None,
            "study_seconds": 0, "break_seconds": 0, "interrupted": False,
        }
        _dirty = True
        flush_stats()
        return sid


def add_lecture_time(session_id, study_seconds, break_seconds, recorded_at=None, count_global=True):
    global _dirty
    if study_seconds < 0 or break_seconds < 0:
        raise ValueError("Duration cannot be negative")
    with _lock:
        stats = _get_stats()
        session = stats["lecture_sessions"][session_id]
        if session["ended_at"] is not None:
            raise ValueError("Cannot add time to a finished session")
        course = stats["courses"].get(session["course_id"])
        lecture = (course["lectures"].get(session["lecture_id"]) if course else None)
        target = lecture if lecture is not None else course
        for key, seconds in (("study_seconds", study_seconds), ("break_seconds", break_seconds)):
            session[key] += seconds
            if target is not None:
                target[key] = target.get(key, 0) + seconds
        now = datetime.fromisoformat(recorded_at) if recorded_at else datetime.now()
        session["last_recorded_at"] = now.isoformat(timespec="seconds")
        today = now.strftime("%Y-%m-%d")
        bucket = session.setdefault("days", {}).setdefault(today, {"study_seconds": 0, "break_seconds": 0})
        bucket["study_seconds"] += study_seconds
        bucket["break_seconds"] += break_seconds
        if not count_global:
            _dirty = True
            return
        day = stats["history"].setdefault(today, {"study_seconds": 0, "tasks": 0})
        if study_seconds:
            _record_activity(stats, now)
            stats["study_seconds"] += study_seconds
            day["study_seconds"] += study_seconds
            hourly = stats["hourly"].setdefault(today, {})
            hour = str(now.hour)
            hourly[hour] = hourly.get(hour, 0) + study_seconds
        stats["break_seconds"] += break_seconds
        day["break_seconds"] = day.get("break_seconds", 0) + break_seconds
        _dirty = True
        if time.monotonic() - _last_save >= SAVE_INTERVAL:
            flush_stats()


def open_pomodoro_session(session_id, course_id, lecture_id, cycle, started_at):
    """Called by the timer's ordered writer, never by a per-second GUI callback."""
    global _dirty
    with _lock:
        data = _get_stats()
        if course_id is not None:
            course = data["courses"][course_id]
            if lecture_id is not None:
                course["lectures"][lecture_id]
        data["lecture_sessions"][session_id] = {
            "course_id": course_id, "lecture_id": lecture_id, "kind": "pomodoro",
            "cycle": cycle, "started_at": started_at, "last_recorded_at": started_at,
            "ended_at": None, "study_seconds": 0, "break_seconds": 0,
            "interrupted": False, "completed_at": None, "days": {},
        }
        _dirty = True


def complete_pomodoro_session(session_id, completed_at):
    global _dirty
    with _lock:
        data = _get_stats()
        session = data["lecture_sessions"][session_id]
        if session.get("completed_at"):
            return
        session["completed_at"] = completed_at
        day = data["history"].setdefault(completed_at[:10], {"study_seconds": 0, "tasks": 0})
        day["pomodoros"] = day.get("pomodoros", 0) + 1
        _dirty = True


def close_pomodoro_session(session_id, ended_at):
    global _dirty
    with _lock:
        _get_stats()["lecture_sessions"][session_id]["ended_at"] = ended_at
        _dirty = True


def course_totals(course):
    """Retain lecture history while also supporting focus directly against a course."""
    if "totals" in course:
        return dict(course["totals"])
    return {key: course.get(key, 0) + sum(lecture.get(key, 0)
            for lecture in course.get("lectures", {}).values())
            for key in ("study_seconds", "break_seconds")}


def finish_lecture_session(session_id):
    global _dirty
    with _lock:
        session = _get_stats()["lecture_sessions"][session_id]
        session["ended_at"] = datetime.now().isoformat(timespec="seconds")
        _dirty = True
        flush_stats()


def recover_lecture_sessions():
    """A previous process ended unexpectedly; never count time while it was closed."""
    global _dirty
    with _lock:
        for session in _get_stats()["lecture_sessions"].values():
            if session["ended_at"] is None:
                session["ended_at"] = session["last_recorded_at"]
                session["interrupted"] = True
                _dirty = True
        flush_stats()


def get_lecture_summary(course_id, lecture_id):
    with _lock:
        stats = _get_stats()
        course = stats["courses"].get(course_id, {})
        lecture = course.get("lectures", {}).get(lecture_id)
        sessions = [dict(s) for s in stats["lecture_sessions"].values()
                    if s["course_id"] == course_id and s["lecture_id"] == lecture_id]
        sessions.reverse()
        return {"lecture": copy.deepcopy(lecture), "sessions": sessions[:50],
                "course_study_seconds": course_totals(course)["study_seconds"],
                "course_break_seconds": course_totals(course)["break_seconds"]}


def add_task_completed():
    global _dirty
    with _lock:
        stats = _get_stats()
        today = _record_activity(stats, datetime.now())
        stats["tasks_completed"] += 1
        stats["history"][today]["tasks"] += 1
        _dirty = True
        flush_stats()


def get_stats_summary():
    return _load_stats()


def load_stats():
    return _load_stats()


atexit.register(flush_stats)
