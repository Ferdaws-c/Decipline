import json
import os
import uuid
from datetime import datetime, timedelta
import re

DB_PATH = "schedules.json"

def load_db():
    if not os.path.exists(DB_PATH):
        return {"active_daily_id": None, "active_weekly_id": None, "schedules": {}}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active_daily_id": None, "active_weekly_id": None, "schedules": {}}

def save_db(data):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def get_daily_schedules():
    db = load_db()
    res = []
    for sid, s in db.get("schedules", {}).items():
        if s.get("type") == "daily":
            res.append({"id": sid, "name": s.get("name")})
    return res

def get_weekly_schedules():
    db = load_db()
    res = []
    for sid, s in db.get("schedules", {}).items():
        if s.get("type") == "weekly":
            res.append({"id": sid, "name": s.get("name")})
    return res

def set_active_schedule(sid):
    db = load_db()
    if sid in db.get("schedules", {}):
        t = db["schedules"][sid]["type"]
        if t == "daily":
            db["active_daily_id"] = sid
        else:
            db["active_weekly_id"] = sid
        db["active_mode"] = t
        save_db(db)

def create_daily_schedule(name, tasks):
    db = load_db()
    sid = str(uuid.uuid4())
    db["schedules"][sid] = {"name": name, "type": "daily", "data": tasks}
    if not db.get("active_daily_id"):
        db["active_daily_id"] = sid
    save_db(db)
    return sid

def create_weekly_schedule(name, weekly_data):
    db = load_db()
    sid = str(uuid.uuid4())
    db["schedules"][sid] = {"name": name, "type": "weekly", "data": weekly_data}
    if not db.get("active_weekly_id"):
        db["active_weekly_id"] = sid
    save_db(db)
    return sid

def rename_schedule(sid, name):
    db = load_db()
    if sid in db.get("schedules", {}):
        db["schedules"][sid]["name"] = name
        save_db(db)

def delete_schedule(sid):
    db = load_db()
    if sid in db.get("schedules", {}):
        del db["schedules"][sid]
        if db.get("active_daily_id") == sid: db["active_daily_id"] = None
        if db.get("active_weekly_id") == sid: db["active_weekly_id"] = None
        save_db(db)

def load_schedule(day_of_week=None):
    db = load_db()
    mode = db.get("active_mode", "daily")
    
    if mode == "daily":
        sid = db.get("active_daily_id")
        if sid and sid in db.get("schedules", {}):
            s = db["schedules"][sid]
            return {"name": s["name"], "tasks": s["data"]}
    else:
        sid = db.get("active_weekly_id")
        if sid and sid in db.get("schedules", {}):
            s = db["schedules"][sid]
            weekly_data = s["data"]
            if not day_of_week:
                day_of_week = datetime.today().strftime("%A")
            tasks = weekly_data.get(day_of_week, [])
            # Also return the weekly data and current day so the UI can build tabs
            return {"name": f"{s['name']} ({day_of_week})", "tasks": tasks, "is_weekly": True, "day": day_of_week, "weekly_data": weekly_data}
            
    return None

def save_active_schedule(tasks, day_of_week=None):
    db = load_db()
    mode = db.get("active_mode", "daily")
    if mode == "daily":
        sid = db.get("active_daily_id")
        if sid and sid in db.get("schedules", {}):
            db["schedules"][sid]["data"] = tasks
            save_db(db)
    else:
        sid = db.get("active_weekly_id")
        if sid and sid in db.get("schedules", {}):
            if not day_of_week:
                day_of_week = datetime.today().strftime("%A")
            db["schedules"][sid]["data"][day_of_week] = tasks
            save_db(db)

def get_display_rows(sched):
    rows = []
    for task in sched.get("tasks", []):
        rows.append([
            task.get("time", ""),
            task.get("text", ""),
            f"{str(task.get('duration', 0)).lower().replace('min', '').strip()} min",
            task.get("notes", ""),
            task.get("completed", False)
        ])
    return rows

def parse_task_time(time_str):
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(time_str.strip(), fmt).time()
        except:
            pass
    return None

def check_postpone_overlap(row_index, minutes, day_of_week=None):
    sched = load_schedule(day_of_week)
    if not sched: return False
    tasks = sched.get("tasks", [])
    if row_index < 0 or row_index >= len(tasks) - 1: return False
    
    t1 = parse_task_time(tasks[row_index].get("time", ""))
    t2 = parse_task_time(tasks[row_index+1].get("time", ""))
    if t1 and t2:
        dt1 = datetime.combine(datetime.today(), t1) + timedelta(minutes=minutes)
        dt2 = datetime.combine(datetime.today(), t2)
        if dt1 >= dt2:
            return True
    return False

def postpone_task(row_index, minutes, mode="push", day_of_week=None):
    sched = load_schedule(day_of_week)
    if not sched: return
    tasks = sched.get("tasks", [])
    if row_index < 0 or row_index >= len(tasks): return
    
    t = parse_task_time(tasks[row_index].get("time", ""))
    if not t: return
    
    dt = datetime.combine(datetime.today(), t) + timedelta(minutes=minutes)
    tasks[row_index]["time"] = dt.strftime("%H:%M")
    
    if mode == "push":
        # Push all subsequent tasks
        for i in range(row_index + 1, len(tasks)):
            t_next = parse_task_time(tasks[i].get("time", ""))
            if t_next:
                dt_next = datetime.combine(datetime.today(), t_next) + timedelta(minutes=minutes)
                tasks[i]["time"] = dt_next.strftime("%H:%M")
    elif mode == "replace":
        # Delete subsequent tasks that have been overlapped
        i = row_index + 1
        while i < len(tasks):
            t_next = parse_task_time(tasks[i].get("time", ""))
            if t_next:
                dt_next = datetime.combine(datetime.today(), t_next)
                if dt_next <= dt:
                    tasks.pop(i)
                    continue
            i += 1
            
    save_active_schedule(tasks, day_of_week)

def complete_task(row_index, day_of_week=None):
    sched = load_schedule(day_of_week)
    if not sched: return
    tasks = sched.get("tasks", [])
    if row_index < 0 or row_index >= len(tasks): return
    # Simply remove the task if it's done
    tasks.pop(row_index)
    save_active_schedule(tasks, day_of_week)

def mark_task_completed(row_index, day_of_week=None):
    sched = load_schedule(day_of_week)
    if not sched: return
    tasks = sched.get("tasks", [])
    if row_index < 0 or row_index >= len(tasks): return
    tasks[row_index]["completed"] = True
    save_active_schedule(tasks, day_of_week)

def get_current_task_index(day_of_week=None):
    """Returns the manually tracked active task index."""
    db = load_db()
    
    # Use a separate key per schedule ID so it tracks correctly
    sid = db.get("active_daily_id") if db.get("active_mode", "daily") == "daily" else db.get("active_weekly_id")
    if not sid: return 0
    
    key = f"active_task_index_{sid}"
    if day_of_week:
        key += f"_{day_of_week}"
        
    return db.get(key, 0)

def advance_task_index(day_of_week=None):
    """Manually advance to the next task."""
    db = load_db()
    sid = db.get("active_daily_id") if db.get("active_mode", "daily") == "daily" else db.get("active_weekly_id")
    if not sid: return
    
    key = f"active_task_index_{sid}"
    if day_of_week:
        key += f"_{day_of_week}"
        
    current = db.get(key, 0)
    db[key] = current + 1
    save_db(db)

def set_active_task_index(index, day_of_week=None):
    """Manually set the active task."""
    db = load_db()
    sid = db.get("active_daily_id") if db.get("active_mode", "daily") == "daily" else db.get("active_weekly_id")
    if not sid: return
    
    key = f"active_task_index_{sid}"
    if day_of_week:
        key += f"_{day_of_week}"
        
    db[key] = index
    save_db(db)

def get_schedule_by_id(sid):
    """Load a specific schedule by its ID."""
    db = load_db()
    if sid in db.get("schedules", {}):
        s = db["schedules"][sid]
        return {"id": sid, "name": s["name"], "type": s["type"], "data": s["data"]}
    return None

def save_schedule_tasks(sid, tasks, day_of_week=None):
    """Save tasks directly to a specific schedule by ID (for the editor)."""
    db = load_db()
    if sid not in db.get("schedules", {}):
        return
    s = db["schedules"][sid]
    if s["type"] == "daily":
        db["schedules"][sid]["data"] = tasks
    else:
        if not day_of_week:
            day_of_week = datetime.today().strftime("%A")
        if day_of_week not in db["schedules"][sid]["data"]:
            db["schedules"][sid]["data"][day_of_week] = []
        db["schedules"][sid]["data"][day_of_week] = tasks
    save_db(db)

def get_schedule_tasks(sid, day_of_week=None):
    """Get tasks from a specific schedule by ID."""
    db = load_db()
    if sid not in db.get("schedules", {}):
        return []
    s = db["schedules"][sid]
    if s["type"] == "daily":
        return s["data"]
    else:
        if not day_of_week:
            day_of_week = datetime.today().strftime("%A")
        return s["data"].get(day_of_week, [])

def create_empty_daily_schedule(name):
    return create_daily_schedule(name, [])

def create_empty_weekly_schedule(name):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return create_weekly_schedule(name, {d: [] for d in days})
