"""First-run choice, simple controls, and safe transitions between interfaces."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog
from app import settings, stats, storage
from app.qt_window import MainWindow
from app.qt_setup import SetupDialog
from app.qt_settings import SettingsDialog
from app.pomodoro import PomodoroState


class BasicModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.path = base / "settings.json"
        for module, name, value in ((settings, "SETTINGS_PATH", str(self.path)),
                                    (stats, "STATS_PATH", str(base / "stats.json")),
                                    (stats, "_stats", None), (stats, "_dirty", False),
                                    (storage, "DB_PATH", str(base / "schedules.json"))):
            p = patch.object(module, name, value)
            p.start()
            self.addCleanup(p.stop)

    def window(self):
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.timer.shutdown)
        return window

    def change_mode(self, window, mode):
        saved = settings.load_settings()
        saved["experience_mode"] = mode
        settings.save_settings(saved)
        window.apply_experience_mode()

    def test_basic_is_default_and_expert_dashboard_is_hidden(self):
        window = self.window()
        self.assertEqual(window.experience_mode, "basic")
        self.assertIs(window.workspace.currentWidget(), window.basic_page)
        self.assertEqual(window.basic_panel.start_btn.text(), "Start")
        self.assertTrue(window.basic_panel.break_btn.isHidden())
        self.assertTrue(window.basic_panel.stop_btn.isHidden())
        self.assertLessEqual(window.width(), 460)
        self.assertLessEqual(window.height(), 600)
        self.assertEqual(len(window.basic_panel.cycles.buttons), 4)
        self.assertEqual(window.mode_tabs.count(), 1)
        self.assertFalse(settings.load_settings()["onboarding_completed"])

    def test_hide_keeps_session_running_in_both_modes_and_close_saves_and_exits(self):
        cid = stats.create_course("Physics")
        window = self.window()
        window.basic_panel.reload_courses(cid)
        window.basic_panel._toggle()
        timer = window.timer
        session_id, worker = timer.session_id, timer._thread
        with patch.object(QApplication, "quit") as quit_app:
            for mode in ("basic", "expert"):
                self.change_mode(window, mode)
                window.show()
                self.app.processEvents()
                with timer._condition:
                    timer._deadline -= 3
                window.title_bar.hide_button.click()
                self.assertFalse(window.isVisible())
                self.assertTrue(timer.is_running)
                self.assertEqual(timer.session_id, session_id)
                self.assertIs(timer._thread, worker)
                quit_app.assert_not_called()
                window.restore_from_tray()
                self.assertTrue(window.isVisible())
            window.title_bar.close_button.click()
            quit_app.assert_called_once()
        self.assertFalse(timer.is_running)
        self.assertFalse(worker.is_alive())
        self.assertEqual(stats.course_totals(stats.get_courses()[cid])["study_seconds"], 6)

    def test_setup_remembers_choice_and_preserves_existing_settings(self):
        settings.save_settings({"focus_time": 45, "daily_prompt": "My prompt", "telegram_token": "keep"})
        dialog = SetupDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.basic_btn.isChecked())
        dialog.choose("expert")
        dialog.save_choice()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        saved = settings.load_settings()
        self.assertTrue(saved["onboarding_completed"])
        self.assertEqual(saved["experience_mode"], "expert")
        self.assertEqual(saved["daily_prompt"], "My prompt")
        self.assertEqual(saved["focus_time"], 45)
        self.assertEqual(saved["telegram_token"], "keep")
        self.assertEqual(self.window().experience_mode, "expert")

    def test_cancelled_or_failed_setup_does_not_mark_onboarding_done(self):
        dialog = SetupDialog()
        self.addCleanup(dialog.deleteLater)
        dialog.reject()
        self.assertFalse(self.path.exists())
        with patch("app.qt_setup.save_settings", return_value=False), \
             patch("app.qt_setup.QMessageBox.warning") as warning:
            dialog.save_choice()
        warning.assert_called_once()
        self.assertFalse(settings.load_settings()["onboarding_completed"])

    def test_basic_duration_is_used_and_stop_saves_study_time(self):
        window = self.window()
        panel = window.basic_panel
        panel.minutes.setValue(10)
        panel._toggle()
        self.assertEqual(window.timer.total, 600)
        self.assertEqual(panel.start_btn.text(), "Pause")
        with window.timer._condition:
            window.timer._deadline -= 120
        panel._toggle()
        self.assertEqual(window.timer.state, PomodoroState.PAUSED)
        self.assertEqual(panel.start_btn.text(), "Resume")
        panel._stop()
        window.timer.shutdown()
        self.app.processEvents()
        self.assertEqual(stats.get_stats_summary()["study_seconds"], 120)
        self.assertEqual(panel.clock.text(), "10:00")
        self.assertIn("saved", panel.status.text())

    def test_course_pomodoro_needs_no_lecture_and_records_separate_breaks(self):
        cid = stats.create_course("Physics")
        window = self.window()
        panel = window.basic_panel
        panel.reload_courses(cid)
        panel._toggle()
        timer = window.timer
        with timer._condition:
            timer._deadline -= 10
            panel._break()
            self.assertEqual(timer.state, PomodoroState.SHORT_BREAK)
            timer._deadline -= 4
        panel._stop()
        timer.shutdown()
        self.app.processEvents()
        saved = stats.get_stats_summary()
        self.assertEqual(saved["study_seconds"], 10)
        self.assertEqual(saved["break_seconds"], 4)
        self.assertEqual(stats.course_totals(saved["courses"][cid])["study_seconds"], 10)
        self.assertEqual(saved["courses"][cid]["lectures"], {})
        self.assertFalse(panel.course.isHidden())

    def test_switching_modes_keeps_one_running_timer_and_selected_course(self):
        cid = stats.create_course("Biology")
        lid = stats.create_lecture(cid, "Cells")
        window = self.window()
        panel = window.basic_panel
        panel.reload_courses(cid, lid)
        panel._toggle()
        timer = window.timer
        session_id = timer.session_id
        with timer._condition:
            timer._deadline -= 5
        self.change_mode(window, "expert")
        self.assertEqual(timer.state, PomodoroState.WORKING)
        self.assertIs(window.workspace.currentWidget(), window.mode_tabs)
        self.assertEqual(panel.lecture.currentData(), lid)
        self.change_mode(window, "basic")
        self.assertEqual(timer.session_id, session_id)
        self.assertEqual(panel.course.currentData(), cid)
        self.assertEqual(panel.start_btn.text(), "Pause")
        panel._stop()
        timer.shutdown()
        self.assertEqual(stats.get_lecture_summary(cid, lid)["lecture"]["study_seconds"], 5)

    def test_clicking_four_dots_selects_cycles_without_crediting_work(self):
        window = self.window()
        panel = window.basic_panel
        for index, button in enumerate(panel.cycles.buttons):
            button.click()
            self.assertEqual(window.timer.selected_cycle, index)
            self.assertTrue(button.isChecked())
            self.assertEqual(sum(b.isChecked() for b in panel.cycles.buttons), 1)
        window.timer.shutdown()
        self.assertEqual(stats.get_stats_summary()["study_seconds"], 0)
        self.assertEqual(sum(d.get("pomodoros", 0) for d in stats.get_stats_summary()["history"].values()), 0)

    def test_timer_controls_use_cached_course_totals_without_waiting_on_disk_writer(self):
        window = self.window()
        panel = window.basic_panel
        with patch.object(stats, "get_courses", side_effect=AssertionError("GUI read during timer control")):
            panel._toggle()
            panel._toggle()
            panel._stop()
            panel.cycles.buttons[2].click()

    def test_settings_show_advanced_options_only_in_expert_and_save_mode(self):
        dialog = SettingsDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertTrue(dialog.telegram_card.isHidden())
        self.assertTrue(all(row.isHidden() for row in dialog._advanced_rows))
        dialog.mode_combo.setCurrentIndex(1)
        self.assertFalse(dialog.telegram_card.isHidden())
        dialog._save()
        self.assertEqual(settings.get_experience_mode(), "expert")
        self.assertTrue(settings.load_settings()["onboarding_completed"])

    def test_switching_from_free_timer_keeps_its_non_study_status_clear(self):
        window = self.window()
        self.change_mode(window, "expert")
        window.timer.start_free(900)
        self.change_mode(window, "basic")
        panel = window.basic_panel
        self.assertEqual(window.timer.state, PomodoroState.FREE_TIMER)
        self.assertEqual(panel.status.text(), "Free timer")
        self.assertIn("not added", panel.session.text())
        panel._stop()
        self.assertEqual(panel.start_btn.text(), "Start")

    def test_basic_timer_does_not_autocomplete_hidden_schedule_tasks(self):
        sid = storage.create_daily_schedule("Routine", [{"text": "Keep this task", "duration": 25}])
        storage.set_active_schedule(sid)
        window = self.window()
        window.basic_panel.minutes.setValue(20)
        window.basic_panel._toggle()
        with window.timer._condition:
            window.timer._deadline -= 660
        window.timer.pause()
        self.change_mode(window, "expert")
        self.app.processEvents()
        window.timer.shutdown()
        self.assertFalse(storage.load_schedule()["tasks"][0].get("completed", False))
        self.assertEqual(storage.get_current_task_index(), 0)
