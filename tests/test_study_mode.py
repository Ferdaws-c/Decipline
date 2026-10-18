"""Course/lecture accounting, mode switching and editable prompt integration."""

import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog
from app import stats, settings, storage
from app.pomodoro import PomodoroTimer, PomodoroState


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for module, key, value in ((stats, "STATS_PATH", str(self.base / "stats.json")),
                                   (stats, "_stats", None), (stats, "_dirty", False),
                                   (settings, "SETTINGS_PATH", str(self.base / "settings.json")),
                                   (storage, "DB_PATH", str(self.base / "schedules.json"))):
            p = patch.object(module, key, value)
            p.start()
            self.addCleanup(p.stop)
        self.cid = stats.create_course("Biology")
        self.lid = stats.create_lecture(self.cid, "Lecture 1: Cells")

    def timer(self, fake_worker=False):
        timer = PomodoroTimer()
        timer.set_context(self.cid, self.lid)
        self.addCleanup(timer.shutdown)
        if fake_worker:
            timer._wake_worker = Mock()
        return timer

    def drain(self, timer):
        timer.reset()
        timer._closed = True
        timer._run()

    def test_focus_break_pause_and_reopen_are_separate(self):
        timer = self.timer(fake_worker=True)
        with patch("app.pomodoro.time.monotonic", return_value=100):
            timer.start()
        with patch("app.pomodoro.time.monotonic", return_value=110.5):
            timer.pause()
        with patch("app.pomodoro.time.monotonic", return_value=900):
            timer.start()
        with patch("app.pomodoro.time.monotonic", return_value=909.5):
            timer.take_break()
        with patch("app.pomodoro.time.monotonic", return_value=939.5):
            timer.pause()
        with patch("app.pomodoro.time.monotonic", return_value=2000):
            timer.start()
        with patch("app.pomodoro.time.monotonic", return_value=2010):
            timer.reset()
        self.drain(timer)
        stats._stats = None
        saved = stats.get_stats_summary()
        self.assertEqual(saved["study_seconds"], 20)
        self.assertEqual(saved["break_seconds"], 40)
        self.assertEqual(sum(sum(day.values()) for day in saved["hourly"].values()), 20)
        lecture = saved["courses"][self.cid]["lectures"][self.lid]
        self.assertEqual(lecture["study_seconds"], 20)
        self.assertEqual(lecture["break_seconds"], 40)
        session = next(iter(saved["lecture_sessions"].values()))
        self.assertIsNotNone(session["ended_at"])
        self.assertEqual(session["study_seconds"], 20)
        self.assertEqual(session["break_seconds"], 40)

    def test_rapid_course_switch_attributes_pending_seconds_correctly(self):
        other = stats.create_course("Physics")
        timer = self.timer(fake_worker=True)
        timer.start()
        with timer._condition:
            timer._deadline -= 10
            timer.reset()
            timer.set_context(other)
            timer.start()
            timer._deadline -= 5
            timer.take_break()
            timer._deadline -= 3
        self.drain(timer)
        saved = stats.get_stats_summary()
        self.assertEqual(stats.course_totals(saved["courses"][self.cid])["study_seconds"], 10)
        self.assertEqual(stats.course_totals(saved["courses"][other])["study_seconds"], 5)
        self.assertEqual(saved["courses"][other]["break_seconds"], 3)
        self.assertEqual(saved["study_seconds"], 15)

    def test_breaks_alone_do_not_create_study_or_streak(self):
        sid = stats.start_lecture_session(self.cid, self.lid)
        stats.add_lecture_time(sid, 0, 60)
        stats.finish_lecture_session(sid)
        saved = stats.get_stats_summary()
        self.assertEqual(saved["study_seconds"], 0)
        self.assertEqual(saved["streak"], 0)
        self.assertEqual(saved["hourly"], {})
        self.assertEqual(saved["break_seconds"], 60)

    def test_interrupted_session_keeps_saved_time_without_counting_closed_time(self):
        sid = stats.start_lecture_session(self.cid, self.lid)
        stats.add_lecture_time(sid, 30, 7)
        stats.flush_stats()
        stats._stats = None
        stats.recover_lecture_sessions()
        session = stats.get_stats_summary()["lecture_sessions"][sid]
        self.assertTrue(session["interrupted"])
        self.assertEqual(session["ended_at"], session["last_recorded_at"])
        self.assertEqual(session["study_seconds"], 30)

    def test_slow_persistence_keeps_controls_responsive_and_flushes_on_quit(self):
        entered, release = threading.Event(), threading.Event()
        timer = self.timer()
        real_add = stats.add_lecture_time

        def slow_add(*args):
            entered.set()
            release.wait(2)
            real_add(*args)

        with patch.object(stats, "add_lecture_time", side_effect=slow_add):
            timer.start()
            with timer._condition:
                timer._deadline -= 2
                timer._condition.notify_all()
            self.assertTrue(entered.wait(1))
            try:
                started = time.perf_counter()
                timer.pause()
                timer.take_break()
                timer.reset()
                self.assertLess(time.perf_counter() - started, .25)
            finally:
                release.set()
            timer.shutdown()
        self.assertEqual(json.loads((self.base / "stats.json").read_text())["study_seconds"], 2)

    def test_scheduled_breaks_are_saved_without_becoming_study(self):
        timer = PomodoroTimer()
        self.addCleanup(timer.shutdown)
        timer._wake_worker = Mock()
        timer.state = PomodoroState.WAITING_FOR_BREAK
        timer.begin_break()
        with timer._condition:
            timer._update(timer._deadline - (timer.total - 15))
        timer.state = PomodoroState.PAUSED
        timer._closed = True
        timer._run()
        saved = stats.get_stats_summary()
        self.assertEqual(saved["break_seconds"], 15)
        self.assertEqual(saved["study_seconds"], 0)

    def test_course_and_lecture_choices_lock_until_stop(self):
        from app.qt_window import MainWindow
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.timer.shutdown)
        panel = window.basic_panel
        panel.reload_courses(self.cid, self.lid)
        panel._toggle()
        self.assertFalse(panel.course.isEnabled())
        self.assertFalse(panel.lecture.isEnabled())
        panel._toggle()
        self.assertEqual(window.timer.state, PomodoroState.PAUSED)
        self.assertFalse(panel.course.isEnabled())
        panel._stop()
        self.assertTrue(panel.course.isEnabled())
        self.assertTrue(panel.lecture.isEnabled())

    def test_prompt_save_copy_reopen_reset_and_cancel(self):
        from app.ai_prompt import get_daily_prompt, get_weekly_prompt, get_default_daily_prompt
        from app.qt_prompt_editor import PromptEditorDialog
        from app.qt_library import LibraryDialog
        settings.save_settings({"focus_time": 45, "telegram_token": "keep-existing"})
        dialog = PromptEditorDialog(kind="weekly")
        self.assertEqual(dialog.tabs.currentIndex(), 1)
        dialog.daily.setPlainText("Custom daily instructions\nJSON please")
        dialog.weekly.setPlainText("Custom weekly instructions")
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(get_daily_prompt(), "Custom daily instructions\nJSON please")
        self.assertEqual(get_weekly_prompt(), "Custom weekly instructions")
        self.assertEqual(settings.load_settings()["focus_time"], 45)
        self.assertEqual(settings.load_settings()["telegram_token"], "keep-existing")
        library = LibraryDialog()
        library._copy_prompt()
        self.assertEqual(self.app.clipboard().text(), get_daily_prompt())
        library._switch_tab("weekly")
        library._copy_prompt()
        self.assertEqual(self.app.clipboard().text(), get_weekly_prompt())
        reopened = PromptEditorDialog()
        reopened.daily.setPlainText("unsaved draft")
        reopened.reject()
        self.assertEqual(get_daily_prompt(), "Custom daily instructions\nJSON please")
        restored = PromptEditorDialog()
        restored.restore_default()
        restored.save()
        self.assertEqual(get_daily_prompt(), get_default_daily_prompt())
        self.assertEqual(get_weekly_prompt(), "Custom weekly instructions")
        for widget in (dialog, library, reopened, restored):
            widget.deleteLater()

    def test_prompt_write_failure_retains_saved_settings_and_editor_text(self):
        from app.qt_prompt_editor import PromptEditorDialog
        settings.save_settings({"daily_prompt": "Original"})
        dialog = PromptEditorDialog()
        dialog.daily.setPlainText("New draft")
        with patch("app.settings.os.replace", side_effect=OSError("disk busy")), \
             patch("app.qt_prompt_editor.QMessageBox.warning") as warning:
            with self.assertLogs("app.settings", level="ERROR"):
                dialog.save()
        warning.assert_called_once()
        self.assertEqual(settings.load_settings()["daily_prompt"], "Original")
        self.assertEqual(dialog.daily.toPlainText(), "New draft")
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
