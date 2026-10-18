"""Regression coverage for freezes, clock drift, persistence and table updates.

Run with: python -m unittest discover -s tests -v
"""

import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication, QTableView

from app import stats, storage
from app.pomodoro import PomodoroState, PomodoroTimer
from app.qt_schedule_model import ScheduleTableModel


class IsolatedStats(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "stats.json")
        self.settings = {"focus_time": 25, "short_break": 5,
                         "long_break": 30, "autocomplete_minutes": 10}
        for target, value in (("app.stats.STATS_PATH", self.path),
                              ("app.stats._stats", None),
                              ("app.stats._dirty", False)):
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch("app.settings.load_settings", side_effect=lambda: self.settings.copy())
        p.start()
        self.addCleanup(p.stop)

    def timer(self, real_worker=False):
        timer = PomodoroTimer()
        if not real_worker:
            timer._wake_worker = Mock()
        self.addCleanup(timer.shutdown)
        return timer


class TimerTests(IsolatedStats):
    def test_paused_reset_returns_promptly_and_reuses_one_worker(self):
        timer = self.timer(real_worker=True)
        timer.start_free(60)
        worker = timer._thread
        timer.pause()
        # Let the worker reach its paused wait, which formerly deadlocked reset.
        time.sleep(0.03)
        started = time.perf_counter()
        for _ in range(30):
            timer.reset()
            timer.start_free(60)
            timer.pause()
        self.assertLess(time.perf_counter() - started, 0.5)
        self.assertIs(timer._thread, worker)
        timer.shutdown()
        self.assertFalse(worker.is_alive())

    def test_clock_catches_up_after_delayed_worker(self):
        timer = self.timer()
        timer.start()
        with timer._condition:
            timer._update(timer._deadline - 1483)
        self.assertEqual(timer.remaining, 1483)
        self.assertEqual(timer._pending_study, 17)

    def test_pause_preserves_fraction_and_excludes_paused_time(self):
        timer = self.timer()
        with patch("app.pomodoro.time.monotonic", return_value=100):
            timer.start_free(20)
        with patch("app.pomodoro.time.monotonic", return_value=102.4):
            timer.pause()
        self.assertEqual(timer.remaining, 18)
        with patch("app.pomodoro.time.monotonic", return_value=1000):
            timer.start()
        self.assertAlmostEqual(timer._deadline, 1017.6)
        with timer._condition:
            timer._update(1001)
        self.assertEqual(timer.remaining, 17)

    def test_focus_autocomplete_and_all_four_cycles(self):
        timer = self.timer()
        timer.on_task_completed = Mock()
        timer.on_work_done = Mock()
        timer.on_break_done = Mock()
        for cycle in range(1, 5):
            timer.start()
            with timer._condition:
                timer._update(timer._deadline - 899)
                timer._update(timer._deadline)
            self.assertEqual(timer.state, PomodoroState.WAITING_FOR_BREAK)
            self.assertFalse(timer.is_running)
            self.assertEqual(timer.cycle, cycle)
            timer.begin_break()
            expected = PomodoroState.LONG_BREAK if cycle == 4 else PomodoroState.SHORT_BREAK
            self.assertEqual(timer.state, expected)
            with timer._condition:
                timer._update(timer._deadline)
            self.assertEqual(timer.state, PomodoroState.WAITING_FOR_WORK)
            self.assertFalse(timer.is_running)
        self.assertEqual(timer.cycle, 0)
        self.assertEqual(timer.on_task_completed.call_count, 4)
        self.assertEqual(timer.on_work_done.call_count, 4)
        self.assertEqual(timer.on_break_done.call_count, 4)

    def test_equal_break_durations_still_select_long_break(self):
        self.settings["long_break"] = self.settings["short_break"]
        timer = self.timer()
        timer.cycle = 4
        timer.state = PomodoroState.WAITING_FOR_BREAK
        timer.begin_break()
        self.assertEqual(timer.state, PomodoroState.LONG_BREAK)

    def test_slow_persistence_does_not_block_controls(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def slow_save(seconds):
            entered.set()
            release.wait(2)

        with patch("app.stats.add_study_time", side_effect=slow_save):
            timer = self.timer(real_worker=True)
            timer.start()
            with timer._condition:
                timer._deadline -= 2
                timer._condition.notify_all()
            self.assertTrue(entered.wait(1))
            started = time.perf_counter()
            timer.pause()
            timer.reset()
            timer.start_free(60)
            self.assertLess(time.perf_counter() - started, 0.25)
            release.set()
            timer.shutdown()

    def test_shutdown_flushes_pending_focus_and_pause_does_not_drop_progress(self):
        timer = self.timer(real_worker=True)
        timer.start()
        with timer._condition:
            timer._deadline -= 3
        timer.pause()
        timer.shutdown()
        saved = json.loads(Path(self.path).read_text())
        self.assertEqual(saved["study_seconds"], 3)

    def test_rapid_pause_then_free_timer_still_flushes_focus(self):
        entered, release, flushed = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)
        real_add, real_flush = stats.add_study_time, stats.flush_stats

        def slow_add(seconds):
            entered.set()
            release.wait(2)
            real_add(seconds)

        def flush():
            real_flush()
            if Path(self.path).exists():
                flushed.set()

        with patch.object(stats, "add_study_time", side_effect=slow_add), \
             patch.object(stats, "flush_stats", side_effect=flush):
            timer = self.timer(real_worker=True)
            timer.start()
            with timer._condition:
                timer._deadline -= 2
                timer._condition.notify_all()
            self.assertTrue(entered.wait(1))
            timer.pause()
            timer.start_free(60)
            release.set()
            self.assertTrue(flushed.wait(1))
            self.assertEqual(json.loads(Path(self.path).read_text())["study_seconds"], 2)
            timer.shutdown()

    def test_free_timer_never_adds_focus_stats(self):
        timer = self.timer()
        timer.on_free_timer_done = Mock()
        timer.start_free(10)
        with timer._condition:
            timer._update(timer._deadline)
        self.assertEqual(timer._pending_study, 0)
        self.assertEqual(timer.state, PomodoroState.IDLE)
        timer.on_free_timer_done.assert_called_once()

    def test_settings_read_at_session_boundaries_not_per_tick(self):
        timer = self.timer()
        timer.start()
        with patch("app.settings.load_settings") as load:
            for left in range(1499, 1400, -1):
                with timer._condition:
                    timer._update(timer._deadline - left)
                timer._get_work_duration()
            load.assert_not_called()
        self.settings["focus_time"] = 10
        timer.reset()
        self.assertEqual(timer.total, 600)


class StatsTests(IsolatedStats):
    def test_writes_are_batched_and_live_summary_is_current(self):
        with patch("app.stats.time.monotonic", return_value=0):
            stats.add_study_time(1)
        with patch("app.stats.time.monotonic", return_value=14):
            stats.add_study_time(13)
        self.assertFalse(Path(self.path).exists())
        self.assertEqual(stats.get_stats_summary()["study_seconds"], 14)
        with patch("app.stats.time.monotonic", return_value=15):
            stats.add_study_time(1)
        self.assertEqual(json.loads(Path(self.path).read_text())["study_seconds"], 15)

    def test_task_updates_preserve_buffered_time_and_concurrent_increments(self):
        def add(_):
            stats.add_study_time(1)
            stats.add_task_completed()
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(add, range(40)))
        stats.flush_stats()
        saved = json.loads(Path(self.path).read_text())
        self.assertEqual(saved["study_seconds"], 40)
        self.assertEqual(saved["tasks_completed"], 40)
        self.assertEqual(saved["streak"], 1)

    def test_failed_atomic_save_preserves_previous_file_and_retries(self):
        stats.add_task_completed()
        original = Path(self.path).read_text()
        stats.add_study_time(5)
        with patch("app.stats.os.replace", side_effect=OSError("disk busy")):
            with self.assertLogs("app.stats", level="ERROR"):
                stats.flush_stats()
        self.assertEqual(Path(self.path).read_text(), original)
        stats.flush_stats()
        self.assertEqual(json.loads(Path(self.path).read_text())["study_seconds"], 5)

    def test_existing_stats_are_preserved_and_snapshots_are_independent(self):
        Path(self.path).write_text(json.dumps({"study_seconds": 120, "tasks_completed": 2,
                                              "history": {"2020-01-01": {"tasks": 2}}}))
        stats.add_study_time(5)
        snapshot = stats.get_stats_summary()
        snapshot["history"].clear()
        stats.flush_stats()
        saved = json.loads(Path(self.path).read_text())
        self.assertEqual(saved["study_seconds"], 125)
        self.assertIn("2020-01-01", saved["history"])


class TableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_small_change_preserves_selection_and_notifies_only_changed_rows(self):
        model = ScheduleTableModel()
        rows = [["09:00", str(i), "25 min", "", False] for i in range(5000)]
        model.set_rows(rows, 0)
        view = QTableView()
        view.setModel(model)
        view.selectRow(2500)
        reset = QSignalSpy(model.modelReset)
        changed = QSignalSpy(model.dataChanged)
        model.set_rows([r.copy() for r in rows], 1)
        self.assertEqual(len(reset), 0)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][0].row(), 0)
        self.assertEqual(changed[0][1].row(), 1)
        self.assertEqual(view.selectionModel().selectedRows()[0].row(), 2500)

    def test_completed_color_takes_precedence_and_noop_has_no_signals(self):
        model = ScheduleTableModel()
        rows = [["", "Task", "25 min", "", True]]
        model.set_rows(rows, 0)
        self.assertEqual(model.data(model.index(0, 1), Qt.ItemDataRole.ForegroundRole).color().name(),
                         "#59d5ae")
        self.assertIsNone(model.data(model.index(0, 1), Qt.ItemDataRole.FontRole))
        spy = QSignalSpy(model.dataChanged)
        model.set_rows(rows, 0)
        self.assertEqual(len(spy), 0)

    def test_window_and_editor_use_model_with_daily_and_weekly_schedules(self):
        from app.qt_window import MainWindow
        from app.qt_task_editor import TaskEditorDialog
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(storage, "DB_PATH", str(Path(directory) / "schedules.json")), \
                 patch.object(stats, "STATS_PATH", str(Path(directory) / "stats.json")):
                tasks = [{"time": "09:00", "text": "Focus", "duration": 25, "notes": ""}]
                daily = storage.create_daily_schedule("Daily", tasks)
                storage.set_active_schedule(daily)
                window = MainWindow()
                self.addCleanup(window.timer.shutdown)
                self.assertEqual(window.table_model.rowCount(), 1)
                window.table.selectRow(0)
                window._mark_active_task_complete()
                self.assertTrue(storage.load_schedule()["tasks"][0]["completed"])
                editor = TaskEditorDialog(sid=daily)
                self.assertEqual(editor.table_model.rowCount(), 1)
                weekly = storage.create_weekly_schedule("Weekly", {"Monday": tasks, "Tuesday": []})
                storage.set_active_schedule(weekly)
                window._load_active_schedule()
                window.day_selector.setCurrentText("Monday")
                self.assertEqual(window.table_model.rowCount(), 1)
                window.day_selector.setCurrentText("Tuesday")
                self.assertEqual(window.table_model.rowCount(), 0)
                editor.deleteLater()
                window.deleteLater()


class DataPathTests(unittest.TestCase):
    def test_packaged_app_finds_old_release_data(self):
        from app.paths import data_path
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            bundle = base / "Decipline"
            bundle.mkdir()
            (base / "schedules.json").write_text("{}")
            with patch.dict(os.environ, {}, clear=False), \
                 patch("app.paths.sys.frozen", True, create=True), \
                 patch("app.paths.sys.executable", str(bundle / "Decipline.exe")):
                os.environ.pop("DECIPLINE_DATA_DIR", None)
                self.assertEqual(Path(data_path("stats.json")), base / "stats.json")
                (bundle / "schedules.json").write_text("{}")
                self.assertEqual(Path(data_path("stats.json")), bundle / "stats.json")

    def test_explicit_data_directory_is_independent_of_working_directory(self):
        from app.paths import data_path
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"DECIPLINE_DATA_DIR": directory}):
                self.assertEqual(Path(data_path("settings.json")), Path(directory) / "settings.json")


if __name__ == "__main__":
    unittest.main()
