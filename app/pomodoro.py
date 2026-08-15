"""
pomodoro.py — Pomodoro timer state machine.

Cycle: 25 min work → 5 min break (×4) → 30 min long break
Alarm fires ONLY on break end. Work end gets a notification popup only.
"""

import threading
import time
from enum import Enum, auto


class PomodoroState(Enum):
    IDLE = auto()
    WORKING = auto()
    SHORT_BREAK = auto()
    LONG_BREAK = auto()
    PAUSED = auto()
    FREE_TIMER = auto()
    WAITING_FOR_WORK = auto()


WORK_DURATION    = 25 * 60   # seconds
SHORT_BREAK      = 5  * 60
LONG_BREAK       = 30 * 60
CYCLES_BEFORE_LONG = 4


class PomodoroTimer:
    """
    Thread-safe Pomodoro state machine.

    Callbacks (all called from background thread):
        on_tick(remaining_seconds, state)      — every second while running
        on_work_done()                         — work session ended, show popup
        on_break_done()                        — break ended, fire alarm
        on_cycle_update(cycle_num)             — cycle number changed (1-4)
    """

    def __init__(self):
        self.state          = PomodoroState.IDLE
        self.cycle          = 0          # 0-based; resets after long break
        self.remaining      = self._get_work_duration()
        self._paused_at     = 0
        self._thread        = None
        self._stop_event    = threading.Event()
        self._pause_event   = threading.Event()
        self._pause_event.set()          # not paused by default

        # Callbacks — set by the window
        self.on_tick           = None
        self.on_work_done      = None
        self.on_break_done     = None
        self.on_cycle_update   = None
        self.on_free_timer_done = None
        self._free_total       = 0

    # ── Public controls ───────────────────────────────────────────────────────

    def _get_work_duration(self):
        from .settings import load_settings
        return load_settings().get("focus_time", 25) * 60
        
    def _get_short_break(self):
        from .settings import load_settings
        return load_settings().get("short_break", 5) * 60
        
    def _get_long_break(self):
        from .settings import load_settings
        return load_settings().get("long_break", 30) * 60

    def start(self):
        """Start or resume."""
        if self.state == PomodoroState.PAUSED:
            self._pause_event.set()
            self.state = self._resume_state
            return
        if self.state == PomodoroState.IDLE:
            self.cycle = 0
            self.remaining = self._get_work_duration()
            self.state = PomodoroState.WORKING
            self._fire_callback(self.on_cycle_update, self.cycle + 1)
        elif self.state == PomodoroState.WAITING_FOR_WORK:
            self.remaining = self._get_work_duration()
            self.state = PomodoroState.WORKING
            self._fire_callback(self.on_cycle_update, self.cycle + 1)
        self._start_thread()

    def pause(self):
        if self.state in (PomodoroState.WORKING,
                          PomodoroState.SHORT_BREAK,
                          PomodoroState.LONG_BREAK,
                          PomodoroState.FREE_TIMER):
            self._resume_state = self.state
            self.state = PomodoroState.PAUSED
            self._pause_event.clear()

    def start_free(self, seconds: int):
        """Start a free-form countdown timer for any duration."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._stop_event.clear()
        self._pause_event.set()
        self._free_total = seconds
        self.remaining   = seconds
        self.state       = PomodoroState.FREE_TIMER
        self._start_thread()

    def reset(self, free_seconds: int = 0):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.state       = PomodoroState.IDLE
        self.cycle       = 0
        self.remaining   = free_seconds if free_seconds else self._get_work_duration()
        self._free_total = free_seconds
        self._stop_event.clear()
        self._pause_event.set()
        self._fire_callback(self.on_tick, self.remaining, self.state)
        self._fire_callback(self.on_cycle_update, 0)

    def begin_break(self):
        """Called after the user dismisses the work-done popup."""
        duration = self._get_short_break() if self.cycle < CYCLES_BEFORE_LONG else self._get_long_break()
        self.state     = (PomodoroState.SHORT_BREAK
                          if duration == self._get_short_break()
                          else PomodoroState.LONG_BREAK)
        self.remaining = duration
        self._start_thread()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _start_thread(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        from .stats import add_study_time
        from .settings import load_settings
        focus_seconds = 0
        task_marked_complete = False
        autocomplete_secs = load_settings().get("autocomplete_minutes", 10) * 60

        while self.remaining > 0 and not self._stop_event.is_set():
            self._pause_event.wait()
            if self._stop_event.is_set():
                break
            self._fire_callback(self.on_tick, self.remaining, self.state)
            time.sleep(1)
            if not self._stop_event.is_set() and self._pause_event.is_set():
                self.remaining -= 1
                
                # Stats and auto-complete ONLY during WORKING state (not Free Timer)
                if self.state == PomodoroState.WORKING:
                    add_study_time(1)
                    focus_seconds += 1
                    if focus_seconds >= autocomplete_secs and not task_marked_complete:
                        task_marked_complete = True
                        if hasattr(self, 'on_task_completed') and self.on_task_completed:
                            self._fire_callback(self.on_task_completed)


        if self._stop_event.is_set():
            return

        # Session ended
        if self.state == PomodoroState.WORKING:
            self.cycle += 1
            self._fire_callback(self.on_cycle_update, self.cycle)
            self._fire_callback(self.on_work_done)
            # Break is triggered by begin_break() after user dismisses popup

        elif self.state in (PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
            if self.cycle >= CYCLES_BEFORE_LONG:
                self.cycle = 0
            self.state = PomodoroState.WAITING_FOR_WORK
            self._fire_callback(self.on_break_done)

        elif self.state == PomodoroState.FREE_TIMER:
            self.state = PomodoroState.IDLE
            self._fire_callback(self.on_free_timer_done)

    def _fire_callback(self, cb, *args):
        if cb:
            try:
                cb(*args)
            except Exception:
                pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    @property
    def is_running(self):
        return self.state not in (PomodoroState.IDLE, PomodoroState.PAUSED)

    @property
    def free_fraction(self) -> float:
        if self._free_total <= 0:
            return 1.0
        return self.remaining / self._free_total

    @staticmethod
    def fmt(seconds: int) -> str:
        m, s = divmod(max(0, seconds), 60)
        return f"{m:02d}:{s:02d}"
