import json
import os
from datetime import datetime, timedelta

STATS_PATH = "stats.json"

def _load_stats():
    if not os.path.exists(STATS_PATH):
        return {
            "streak": 0,
            "last_active_date": None,
            "study_seconds": 0,
            "tasks_completed": 0,
            "history": {}  # Format: {"YYYY-MM-DD": {"study_seconds": 0, "tasks": 0}}
        }
    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "streak": 0,
            "last_active_date": None,
            "study_seconds": 0,
            "tasks_completed": 0,
            "history": {}
        }

def _save_stats(data):
    try:
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _get_today_str():
    return datetime.today().strftime("%Y-%m-%d")

def check_streak():
    """Check if the streak should be reset due to missed days."""
    stats = _load_stats()
    today_str = _get_today_str()
    last_active = stats.get("last_active_date")
    
    if last_active and last_active != today_str:
        last_date = datetime.strptime(last_active, "%Y-%m-%d").date()
        today_date = datetime.today().date()
        
        # If more than 1 day has passed, reset streak
        if (today_date - last_date).days > 1:
            stats["streak"] = 0
            _save_stats(stats)
            
    return stats.get("streak", 0)

def record_activity():
    """Mark the user as active for today, incrementing streak if applicable."""
    stats = _load_stats()
    today_str = _get_today_str()
    last_active = stats.get("last_active_date")
    
    if last_active != today_str:
        last_date = datetime.strptime(last_active, "%Y-%m-%d").date() if last_active else None
        today_date = datetime.today().date()
        
        if last_date and (today_date - last_date).days == 1:
            stats["streak"] += 1
        elif not last_date or (today_date - last_date).days > 1:
            stats["streak"] = 1
            
        stats["last_active_date"] = today_str
        
        # Initialize today's history
        if today_str not in stats["history"]:
            stats["history"][today_str] = {"study_seconds": 0, "tasks": 0}
            
        _save_stats(stats)

def add_study_time(seconds):
    """Add seconds to total and today's study time, with hourly granularity."""
    record_activity()
    stats = _load_stats()
    today_str = _get_today_str()
    current_hour = str(datetime.now().hour)

    stats["study_seconds"] = stats.get("study_seconds", 0) + seconds

    if today_str not in stats["history"]:
        stats["history"][today_str] = {"study_seconds": 0, "tasks": 0}
    stats["history"][today_str]["study_seconds"] += seconds

    # Hourly breakdown for 24h chart
    if "hourly" not in stats:
        stats["hourly"] = {}
    if today_str not in stats["hourly"]:
        stats["hourly"][today_str] = {}
    if current_hour not in stats["hourly"][today_str]:
        stats["hourly"][today_str][current_hour] = 0
    stats["hourly"][today_str][current_hour] += seconds

    _save_stats(stats)

def add_task_completed():
    """Increment the completed task count."""
    record_activity()
    stats = _load_stats()
    today_str = _get_today_str()
    
    stats["tasks_completed"] = stats.get("tasks_completed", 0) + 1
    
    if today_str not in stats["history"]:
        stats["history"][today_str] = {"study_seconds": 0, "tasks": 0}
    stats["history"][today_str]["tasks"] += 1
    
    _save_stats(stats)

def get_stats_summary():
    """Return a summary of trends."""
    stats = _load_stats()
    return stats

def load_stats():
    """Public alias for loading raw stats (used by Trends dialog)."""
    return _load_stats()
