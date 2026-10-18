import json
import os
import uuid
from datetime import datetime, timedelta
import re
import tempfile
from .paths import data_path

DB_PATH = data_path("schedules.json")

def load_db():
    if not os.path.exists(DB_PATH):
        return {"active_daily_id": None, "active_weekly_id": None, "schedules": {}}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active_daily_id": None, "active_weekly_id": None, "schedules": {}}

def save_db(data):
    """Replace the library atomically; let callers report failed changes."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                dir=os.path.dirname(os.path.abspath(DB_PATH)), delete=False) as f:
            temporary = f.name
            json.dump(data, f, indent=2)
        os.replace(temporary, DB_PATH)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def _schedule_name(name):
    name = name.strip()
    if not name:
        raise ValueError("Enter a schedule name.")
    return name

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
    name = _schedule_name(name)
    db = load_db()
    sid = str(uuid.uuid4())
    db["schedules"][sid] = {"name": name, "type": "daily", "data": tasks}
    if not db.get("active_daily_id"):
        db["active_daily_id"] = sid
    save_db(db)
    return sid

def create_weekly_schedule(name, weekly_data):
    name = _schedule_name(name)
    db = load_db()
    sid = str(uuid.uuid4())
    db["schedules"][sid] = {"name": name, "type": "weekly", "data": weekly_data}
    if not db.get("active_weekly_id"):
        db["active_weekly_id"] = sid
    save_db(db)
    return sid

def rename_schedule(sid, name):
    name = _schedule_name(name)
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
        for key in list(db):
            if key == f"active_task_index_{sid}" or key.startswith(f"active_task_index_{sid}_"):
                del db[key]
        save_db(db)

def load_schedule(day_of_week=None):
    db = load_db()
    mode = db.get("active_mode", "daily")
    
    if mode == "daily":
        sid = db.get("active_daily_id")
        if sid and sid in db.get("schedules", {}):
            s = db["schedules"][sid]
            return {"name": s["name"], "tasks": s["data"],
                    "active_task_index": db.get(f"active_task_index_{sid}", 0)}
    else:
        sid = db.get("active_weekly_id")
        if sid and sid in db.get("schedules", {}):
            s = db["schedules"][sid]
            weekly_data = s["data"]
            if not day_of_week:
                day_of_week = datetime.today().strftime("%A")
            tasks = weekly_data.get(day_of_week, [])
            # Also return the weekly data and current day so the UI can build tabs
            return {"name": f"{s['name']} ({day_of_week})", "tasks": tasks,
                    "is_weekly": True, "day": day_of_week, "weekly_data": weekly_data,
                    "active_task_index": db.get(f"active_task_index_{sid}_{day_of_week}", 0)}
            
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


def capture_schedule_target(day_of_week=None):
    """Bind a focus session to a stable task, even if the user changes the view."""
    db = load_db()
    weekly = db.get("active_mode", "daily") == "weekly"
    sid = db.get("active_weekly_id" if weekly else "active_daily_id")
    schedule = db.get("schedules", {}).get(sid)
    if not schedule:
        return None
    day = (day_of_week or datetime.today().strftime("%A")) if weekly else None
    tasks = schedule["data"].get(day, []) if weekly else schedule["data"]
    key = f"active_task_index_{sid}" + (f"_{day}" if day else "")
    index = max(0, db.get(key, 0))
    while index < len(tasks) and tasks[index].get("completed"):
        index += 1
    if index >= len(tasks):
        return None
    task = tasks[index]
    identity = task.get("_decipline_task_id")
    unique = bool(identity) and sum(t.get("_decipline_task_id") == identity for t in tasks) == 1
    if not unique or db.get(key, 0) != index:
        if not unique:
            task["_decipline_task_id"] = str(uuid.uuid4())
        db[key] = index
        save_db(db)
    return {"schedule_id": sid, "day": day, "task_id": task["_decipline_task_id"],
            "text": task.get("text", "Task")}


def complete_schedule_target(target):
    """Complete only the originally timed task; deleted or already completed tasks are skipped."""
    db = load_db()
    sid, day = target["schedule_id"], target["day"]
    schedule = db.get("schedules", {}).get(sid)
    if not schedule:
        return False
    tasks = schedule["data"].get(day, []) if schedule["type"] == "weekly" else schedule["data"]
    for index, task in enumerate(tasks):
        if task.get("_decipline_task_id") != target["task_id"]:
            continue
        if task.get("completed"):
            return False
        task["completed"] = True
        key = f"active_task_index_{sid}" + (f"_{day}" if day else "")
        if db.get(key, 0) == index:
            next_index = index + 1
            while next_index < len(tasks) and tasks[next_index].get("completed"):
                next_index += 1
            db[key] = next_index
        save_db(db)
        return True
    return False

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

def get_schedule_position(sid, day_of_week=None):
    key = f"active_task_index_{sid}" + (f"_{day_of_week}" if day_of_week else "")
    return load_db().get(key, 0)


def save_schedule_tasks(sid, tasks, day_of_week=None, active_index=None):
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
    key = f"active_task_index_{sid}" + (f"_{day_of_week}" if s["type"] == "weekly" else "")
    current = db.get(key, 0) if active_index is None else active_index
    db[key] = max(0, min(current, len(tasks)))
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
