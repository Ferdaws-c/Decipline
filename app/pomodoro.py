"""Pomodoro state machine with one interruptible, monotonic-clock worker."""

import logging
import math
import threading
import time
import uuid
from datetime import datetime
from enum import Enum, auto


class PomodoroState(Enum):
    IDLE = auto()
    WORKING = auto()
    SHORT_BREAK = auto()
    LONG_BREAK = auto()
    PAUSED = auto()
    FREE_TIMER = auto()
    WAITING_FOR_WORK = auto()
    WAITING_FOR_BREAK = auto()


WORK_DURATION = 25 * 60
SHORT_BREAK = 5 * 60
LONG_BREAK = 30 * 60
CYCLES_BEFORE_LONG = 4
_RUNNING = {PomodoroState.WORKING, PomodoroState.SHORT_BREAK,
            PomodoroState.LONG_BREAK, PomodoroState.FREE_TIMER}


class PomodoroTimer:
    """Callbacks run on the worker (or caller); Qt clients must use signals.

    Controls wake one worker instead of joining/replacing threads on the UI
    thread. Deadlines exclude paused time and do not drift with disk I/O.
    """

    def __init__(self):
        self._condition = threading.Condition(threading.RLock())
        self._thread = None
        self._closed = False
        self.state = PomodoroState.IDLE
        self.cycle = 0
        self._settings = {}
        self._reload_settings()
        self.remaining = self.total = self._get_work_duration()
        self._time_left = float(self.remaining)
        self._deadline = None
        self._free_total = 0
        self._focus_seconds = 0
        self._task_marked_complete = False
        self._track_tasks = True
        self._pending_study = 0
        self._pending_break = 0
        self._flush_requested = False
        self.course_id = self.lecture_id = self.session_id = None
        self.focus_context = None
        self._events = []
        self._focus_resume = None
        self.on_tick = None
        self.on_work_done = None
        self.on_focus_completed = None
        self.on_break_done = None
        self.on_cycle_update = None
        self.on_free_timer_done = None
        self.on_task_completed = None
        self.on_stats_update = None

    def _reload_settings(self):
        from .settings import load_settings
        self._settings = load_settings()

    def _get_work_duration(self):
        return self._settings.get("focus_time", 25) * 60

    def _get_short_break(self):
        return self._settings.get("short_break", 5) * 60

    def _get_long_break(self):
        return self._settings.get("long_break", 30) * 60

    def _wake_worker(self):
        if self._closed:
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True,
                                            name="DeciplineTimer")
            self._thread.start()
        self._condition.notify_all()

    def _begin(self, state, duration):
        self.state = state
        self.total = self.remaining = duration
        self._time_left = float(duration)
        self._deadline = time.monotonic() + duration
        self._fire_callback(self.on_tick, self.remaining, self.state)
        self._wake_worker()

    def start(self, work_seconds=None, track_tasks=True, focus_context=None):
        """Start or resume a focus session."""
        with self._condition:
            if self._closed or self.state in _RUNNING:
                return
            if self.state == PomodoroState.PAUSED:
                self.state = self._resume_state
                self._deadline = time.monotonic() + self._time_left
                self._fire_callback(self.on_tick, self.remaining, self.state)
                self._wake_worker()
                return
            self._close_session()
            if self.state == PomodoroState.IDLE or self.cycle >= CYCLES_BEFORE_LONG:
                self.cycle = 0
            self._reload_settings()
            self._focus_seconds = 0
            self._task_marked_complete = False
            self._track_tasks = track_tasks
            self.focus_context = focus_context
            self.session_id = str(uuid.uuid4())
            self._events.append(("open", self.session_id, self.course_id, self.lecture_id,
                                 self.cycle + 1, self._now()))
            self._fire_callback(self.on_cycle_update, self.cycle + 1)
            self._begin(PomodoroState.WORKING, work_seconds or self._get_work_duration())

    @staticmethod
    def _now():
        return datetime.now().isoformat(timespec="seconds")

    def _close_session(self):
        if self.session_id:
            self._events.append(("close", self.session_id, self._now()))
            self.session_id = None
            self.focus_context = None

    def set_context(self, course_id=None, lecture_id=None):
        with self._condition:
            if self.session_id:
                raise ValueError("Stop the current session before changing course.")
            self.course_id, self.lecture_id = course_id, lecture_id

    @property
    def selected_cycle(self):
        state = self._resume_state if self.state == PomodoroState.PAUSED else self.state
        completed = state in (PomodoroState.WAITING_FOR_BREAK, PomodoroState.SHORT_BREAK,
                              PomodoroState.LONG_BREAK) and self._focus_resume is None
        return max(0, min(3, self.cycle - 1 if completed else self.cycle))

    def select_cycle(self, index):
        """Save partial progress and prepare this slot; selecting never credits a completion."""
        if index not in range(4):
            raise ValueError("Choose cycle 1 to 4")
        with self._condition:
            if self._closed:
                return
            self._update(time.monotonic())
            self._close_session()
            self._focus_resume = None
            self.cycle = index
            self.state = PomodoroState.WAITING_FOR_WORK
            self._deadline = None
            self.total = self.remaining = self._get_work_duration()
            self._time_left = float(self.remaining)
            self._flush_requested = True
            self._fire_callback(self.on_tick, self.remaining, self.state)
            self._fire_callback(self.on_cycle_update, index + 1)
            self._wake_worker()

    def take_break(self):
        """An early break preserves the unfinished focus countdown and its course."""
        with self._condition:
            effective = self._resume_state if self.state == PomodoroState.PAUSED else self.state
            if effective != PomodoroState.WORKING:
                return
            self._update(time.monotonic())
            if self.state == PomodoroState.WAITING_FOR_BREAK:
                self.begin_break()
                return
            self._focus_resume = (self._time_left, self.remaining, self.total)
            self._begin(PomodoroState.SHORT_BREAK, self._get_short_break())

    def end_break(self):
        with self._condition:
            effective = self._resume_state if self.state == PomodoroState.PAUSED else self.state
            if effective not in (PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
                return
            self._update(time.monotonic())
            effective = self._resume_state if self.state == PomodoroState.PAUSED else self.state
            if effective in (PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
                self._finish_break()
            self._flush_requested = True
            self._wake_worker()

    def _finish_break(self):
        self._deadline = None
        if self._focus_resume is not None:
            self._time_left, self.remaining, self.total = self._focus_resume
            self._focus_resume = None
            self.state = PomodoroState.PAUSED
            self._resume_state = PomodoroState.WORKING
        else:
            if self.cycle >= CYCLES_BEFORE_LONG:
                self.cycle = 0
            self._close_session()
            self.state = PomodoroState.WAITING_FOR_WORK
        self._fire_callback(self.on_tick, self.remaining, self.state)

    def pause(self):
        with self._condition:
            if self.state in _RUNNING:
                self._update(time.monotonic())
                if self.state in _RUNNING:
                    self._resume_state = self.state
                    self.state = PomodoroState.PAUSED
                    self._deadline = None
                self._flush_requested = True
                self._condition.notify_all()

    def start_free(self, seconds: int):
        if seconds <= 0:
            raise ValueError("Timer duration must be positive")
        with self._condition:
            if self._closed:
                return
            self._update(time.monotonic())
            self._close_session()
            self._focus_resume = None
            self._free_total = seconds
            self._flush_requested = True
            self._begin(PomodoroState.FREE_TIMER, seconds)

    def reset(self, free_seconds: int = 0):
        with self._condition:
            if self._closed:
                return
            self._update(time.monotonic())
            self._close_session()
            self._focus_resume = None
            self._reload_settings()
            self.state = PomodoroState.IDLE
            self.cycle = 0
            self.total = self.remaining = free_seconds or self._get_work_duration()
            self._time_left = float(self.remaining)
            self._free_total = free_seconds
            self._deadline = None
            self._flush_requested = True
            self._fire_callback(self.on_tick, self.remaining, self.state)
            self._fire_callback(self.on_cycle_update, 0)
            self._condition.notify_all()

    def begin_break(self):
        with self._condition:
            if self._closed or self.state != PomodoroState.WAITING_FOR_BREAK:
                return
            self._reload_settings()
            long_break = self.cycle >= CYCLES_BEFORE_LONG
            self._begin(PomodoroState.LONG_BREAK if long_break else PomodoroState.SHORT_BREAK,
                        self._get_long_break() if long_break else self._get_short_break())

    def _update(self, now):
        """Advance under the condition lock, including time between ticks."""
        if self.state not in _RUNNING or self._deadline is None:
            return
        self._time_left = max(0.0, self._deadline - now)
        remaining = math.ceil(self._time_left)
        elapsed = self.remaining - remaining
        if elapsed <= 0:
            return
        self.remaining = remaining
        if self.state == PomodoroState.WORKING:
            if self.course_id is None:
                self._pending_study += elapsed
            if self.session_id:
                self._events.append(("time", self.session_id, elapsed, 0, self._now(), self.course_id is not None))
            self._focus_seconds += elapsed
            if (self._track_tasks and not self._task_marked_complete and self._focus_seconds >=
                    self._settings.get("autocomplete_minutes", 10) * 60):
                self._task_marked_complete = True
                self._fire_callback(self.on_task_completed)
        elif self.state in (PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
            if self.course_id is None:
                self._pending_break += elapsed
            if self.session_id:
                self._events.append(("time", self.session_id, 0, elapsed, self._now(), self.course_id is not None))
        self._fire_callback(self.on_tick, self.remaining, self.state)
        if self.remaining:
            return
        finished_state = self.state
        self._deadline = None
        self._flush_requested = True
        if finished_state == PomodoroState.WORKING:
            if self.session_id:
                self._events.append(("complete", self.session_id, self._now()))
                self._fire_callback(self.on_focus_completed, self.session_id, self.focus_context)
            self.cycle += 1
            self.state = PomodoroState.WAITING_FOR_BREAK
            self._fire_callback(self.on_cycle_update, self.cycle)
            self._fire_callback(self.on_work_done)
        elif finished_state in (PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
            self._finish_break()
            self._fire_callback(self.on_break_done)
        else:
            self.state = PomodoroState.IDLE
            self._fire_callback(self.on_free_timer_done)

    def _run(self):
        from .stats import add_study_time, add_break_time, flush_stats
        while True:
            with self._condition:
                self._update(time.monotonic())
                seconds, self._pending_study = self._pending_study, 0
                break_seconds, self._pending_break = self._pending_break, 0
                events, self._events = self._events, []
                flush_requested, self._flush_requested = self._flush_requested, False
                inactive = self.state not in _RUNNING
                observed = (self.state, self._deadline)
                closed = self._closed
            # Disk work stays outside the timer lock and the GUI thread.
            self._persist_events(events)
            if seconds:
                add_study_time(seconds)
            if break_seconds:
                add_break_time(break_seconds)
            if inactive or closed or flush_requested:
                flush_stats()
            if seconds or break_seconds or events:
                self._fire_callback(self.on_stats_update)
            if closed:
                return
            with self._condition:
                # A control may have changed state during persistence.
                if (self._closed or self._events or self._pending_study or self._pending_break or self._flush_requested or
                        observed != (self.state, self._deadline)):
                    continue
                timeout = None
                if self.state in _RUNNING:
                    timeout = max(0.001, self._deadline - time.monotonic() -
                                  max(0, self.remaining - 1))
                self._condition.wait(timeout)

    @staticmethod
    def _persist_events(events):
        from . import stats
        writers = {"open": stats.open_pomodoro_session, "time": stats.add_lecture_time,
                   "complete": stats.complete_pomodoro_session, "close": stats.close_pomodoro_session}
        for action, *args in events:
            writers[action](*args)

    def shutdown(self):
        """Flush progress and stop the worker when the application quits."""
        with self._condition:
            self._update(time.monotonic())
            self._close_session()
            self._deadline = None
            self._closed = True
            self._condition.notify_all()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)
        from .stats import flush_stats
        flush_stats()

    @staticmethod
    def _fire_callback(cb, *args):
        if cb:
            try:
                cb(*args)
            except Exception:
                logging.getLogger(__name__).exception("Timer callback failed")

    @property
    def is_running(self):
        return not self._closed and self.state in _RUNNING

    @property
    def free_fraction(self) -> float:
        return self.remaining / self._free_total if self._free_total > 0 else 1.0

    @staticmethod
    def fmt(seconds: int) -> str:
        m, s = divmod(max(0, seconds), 60)
        return f"{m:02d}:{s:02d}"
