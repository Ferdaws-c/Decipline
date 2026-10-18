"""Study evaluation from saved durations, with no inferred Pomodoro completions."""
from collections import defaultdict
from datetime import date, timedelta
from .stats import course_totals


def evaluate(data, days=7, course_id=None, today=None):
    today = today or date.today()
    start = today - timedelta(days=days - 1) if days else date.min
    daily = defaultdict(lambda: {"study_seconds": 0, "break_seconds": 0, "pomodoros": 0})
    courses = {cid: {"name": c["name"] + (" (removed)" if c.get("deleted") else ""), "study_seconds": 0, "break_seconds": 0, "pomodoros": 0}
               for cid, c in data.get("courses", {}).items()}
    selected_course = data.get("courses", {}).get(course_id, {})
    lectures = {lid: {"name": lecture["name"] + (" (removed)" if lecture.get("deleted") else ""), "study_seconds": 0, "break_seconds": 0, "pomodoros": 0}
                for lid, lecture in selected_course.get("lectures", {}).items()}
    lectures[None] = {"name": "Whole course", "study_seconds": 0, "break_seconds": 0, "pomodoros": 0}
    for session in data.get("lecture_sessions", {}).values():
        cid = session.get("course_id")
        buckets = session.get("days") or {session["started_at"][:10]: session}
        for day, bucket in buckets.items():
            try:
                day_date = date.fromisoformat(day)
            except ValueError:
                continue
            if not start <= day_date <= today:
                continue
            for key in ("study_seconds", "break_seconds"):
                seconds = bucket.get(key, 0)
                if cid in courses:
                    courses[cid][key] += seconds
                if course_id is not None and cid == course_id:
                    daily[day][key] += seconds
                    lectures.get(session.get("lecture_id"), lectures[None])[key] += seconds
        completed = session.get("completed_at")
        if completed and start <= date.fromisoformat(completed[:10]) <= today:
            if cid in courses:
                courses[cid]["pomodoros"] += 1
            if course_id is not None and cid == course_id:
                daily[completed[:10]]["pomodoros"] += 1
                lectures.get(session.get("lecture_id"), lectures[None])["pomodoros"] += 1
    if course_id is None:
        for day, bucket in data.get("history", {}).items():
            try:
                day_date = date.fromisoformat(day)
            except ValueError:
                continue
            if start <= day_date <= today:
                for key in ("study_seconds", "break_seconds", "pomodoros"):
                    daily[day][key] = bucket.get(key, 0)
    # Course counters preserve older imported lecture totals even when dated sessions are absent.
    if days is None:
        for cid, course in data.get("courses", {}).items():
            courses[cid].update(course_totals(course))
        for lid, row in lectures.items():
            original = selected_course if lid is None else selected_course.get("lectures", {}).get(lid, {})
            row.update({key: original.get(key, 0) for key in ("study_seconds", "break_seconds")})
    totals = {key: sum(day[key] for day in daily.values())
              for key in ("study_seconds", "break_seconds", "pomodoros")}
    if days is None:
        target = data if course_id is None else courses.get(course_id, {})
        totals.update({key: target.get(key, 0) for key in ("study_seconds", "break_seconds")})
    active_days = sum(day["study_seconds"] > 0 for day in daily.values())
    dated_study = sum(day["study_seconds"] for day in daily.values())
    if days:
        first = start
    else:
        first = min((date.fromisoformat(day) for day in daily), default=today - timedelta(days=6))
    span = (today - first).days + 1
    # At most 32 columns; longer histories use labelled calendar months/years.
    mode = "day" if span <= 31 else "week" if span <= 180 else "month" if span <= 730 else "year"
    def bucket_key(day):
        if mode == "day":
            return day
        if mode == "week":
            return day - timedelta(days=day.weekday())
        return day.replace(day=1) if mode == "month" else day.replace(month=1, day=1)
    chart = defaultdict(int)
    cursor = first
    while cursor <= today:
        chart[bucket_key(cursor)] += daily.get(cursor.isoformat(), {}).get("study_seconds", 0)
        cursor += timedelta(days=1)
    series = [(day, value) for day, value in sorted(chart.items())]
    general = {"name": "General study", "study_seconds": max(0, totals["study_seconds"] - sum(c["study_seconds"] for c in courses.values())),
               "break_seconds": max(0, totals["break_seconds"] - sum(c["break_seconds"] for c in courses.values())),
               "pomodoros": max(0, totals["pomodoros"] - sum(c["pomodoros"] for c in courses.values()))}
    rows = [(cid, row) for cid, row in courses.items() if (course_id is None or cid == course_id)
            and (not data["courses"][cid].get("deleted") or any(row[key]
                 for key in ("study_seconds", "break_seconds", "pomodoros")))]
    if course_id is None and any(general[key] for key in ("study_seconds", "break_seconds", "pomodoros")):
        rows.append((None, general))
    rows.sort(key=lambda item: item[1]["study_seconds"], reverse=True)
    lecture_rows = sorted(lectures.items(), key=lambda item: item[1]["study_seconds"], reverse=True)
    lecture_rows = [(lid, row) for lid, row in lecture_rows
                    if (lid is not None and not selected_course["lectures"][lid].get("deleted"))
                    or any(row[key] for key in ("study_seconds", "break_seconds", "pomodoros"))]
    return {**totals, "active_days": active_days, "average": dated_study / active_days if active_days else 0,
            "undated_study": max(0, totals["study_seconds"] - dated_study),
            "series": series, "bucket": mode, "courses": rows, "lectures": lecture_rows, "days": days}
