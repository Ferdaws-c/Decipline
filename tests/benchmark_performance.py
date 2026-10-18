"""Compare table refresh and timer controls with an earlier Git revision.

python tests/benchmark_performance.py --baseline 5f439ef
Uses temporary schedules and statistics; never touches personal data.
"""

import argparse
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt6.QtWidgets import QApplication
from app import stats, storage, settings
from app.pomodoro import PomodoroTimer
from app.qt_window import MainWindow


def original_module(revision, filename):
    source = subprocess.check_output(["git", "show", f"{revision}:app/{filename}.py"],
                                     encoding="utf-8")
    namespace = {"__name__": f"app._baseline_{filename}", "__package__": "app"}
    exec(compile(source, f"baseline/{filename}.py", "exec"), namespace)
    return namespace


def median_ms(action, repeats=7):
    measurements = []
    for _ in range(repeats):
        start = time.perf_counter()
        action()
        measurements.append((time.perf_counter() - start) * 1000)
    return statistics.median(measurements)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="5f439ef")
    args = parser.parse_args()
    app = QApplication([])
    old_window = original_module(args.baseline, "qt_window")["MainWindow"]
    old_timer = original_module(args.baseline, "pomodoro")["PomodoroTimer"]
    with tempfile.TemporaryDirectory() as directory:
        with patch.object(storage, "DB_PATH", str(Path(directory) / "schedules.json")), \
             patch.object(stats, "STATS_PATH", str(Path(directory) / "stats.json")), \
             patch.object(settings, "load_settings", return_value={**settings.DEFAULT_SETTINGS, "experience_mode": "expert"}):
            for count in (100, 1000, 5000):
                tasks = [{"time": "09:00", "text": f"Task {i}", "duration": 25,
                          "notes": "Focus session", "completed": False} for i in range(count)]
                storage.set_active_schedule(storage.create_daily_schedule("Benchmark", tasks))
                before, after = old_window(), MainWindow()
                before.show()
                after.show()
                app.processEvents()

                def refresh(window):
                    storage.advance_task_index()
                    window._refresh_table()
                    app.processEvents()

                old_ms = median_ms(lambda: refresh(before))
                new_ms = median_ms(lambda: refresh(after))
                print(f"{count:5d} tasks, refresh + paint: {old_ms:.2f} -> {new_ms:.2f} ms "
                      f"({old_ms / max(new_ms, .001):.1f}x)")
                before.timer.shutdown()
                after.timer.shutdown()
                before.close()
                after.close()
            for label, timer_type in (("Before", old_timer), ("After", PomodoroTimer)):
                timer = timer_type()
                timer.start_free(60)
                time.sleep(.05)
                timer.pause()
                time.sleep(1.1 if label == "Before" else .03)
                start = time.perf_counter()
                timer.reset()
                print(f"{label} paused reset: {(time.perf_counter() - start) * 1000:.3f} ms")
                if hasattr(timer, "shutdown"):
                    timer.shutdown()


if __name__ == "__main__":
    main()
