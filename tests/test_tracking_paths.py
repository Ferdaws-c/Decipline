"""Explicit course/schedule routing, safe task completion and quick mode changes."""
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from app import settings, stats, storage
from app.pomodoro import PomodoroState as State
from app.qt_window import MainWindow
from app.qt_task_editor import SingleTaskDialog


class TrackingPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        for module, key, value in ((stats, 'STATS_PATH', str(self.base / 'stats.json')),
                                   (stats, '_stats', None), (stats, '_dirty', False),
                                   (storage, 'DB_PATH', str(self.base / 'schedules.json')),
                                   (settings, 'SETTINGS_PATH', str(self.base / 'settings.json'))):
            context = patch.object(module, key, value)
            context.start()
            self.addCleanup(context.stop)
        self.cid = stats.create_course('Biology')

    def routine(self, weekly=False):
        tasks = [{'text': 'First task', 'duration': 25}, {'text': 'Second task', 'duration': 25}]
        sid = (storage.create_weekly_schedule('Weekly', {'Monday': tasks, 'Tuesday': [{'text': 'Tuesday task'}]})
               if weekly else storage.create_daily_schedule('Routine', tasks))
        storage.set_active_schedule(sid)
        return sid

    def window(self, expert=False):
        settings.save_settings({**settings.load_settings(), 'experience_mode': 'expert' if expert else 'basic'})
        window = MainWindow()
        window._notify_phase = Mock()
        window._show_focus_completion = Mock()
        window.basic_panel.reload_courses(self.cid)
        def close():
            window.timer.shutdown()
            self.app.processEvents()
            window.deleteLater()
            self.app.processEvents()
        self.addCleanup(close)
        return window

    def finish(self, window):
        with window.timer._condition:
            window.timer._update(window.timer._deadline)
        self.app.processEvents()

    def test_top_bar_switch_preserves_running_session_and_saved_preferences(self):
        window = self.window()
        settings.save_settings({**settings.load_settings(), 'daily_prompt': 'Keep my prompt'})
        panel = window.basic_panel
        panel._toggle()
        sid, worker = window.timer.session_id, window.timer._thread
        self.assertEqual(window.title_bar.mode_button.text(), 'Expert mode')
        window.title_bar.mode_button.click()
        self.assertEqual(window.experience_mode, 'expert')
        self.assertEqual(settings.get_experience_mode(), 'expert')
        self.assertEqual(window.title_bar.mode_button.text(), 'Basic mode')
        self.assertTrue(window.timer.is_running)
        self.assertEqual(window.timer.session_id, sid)
        window.title_bar.mode_button.click()
        self.assertEqual(window.experience_mode, 'basic')
        self.assertTrue(window.timer.is_running)
        self.assertEqual(window.timer.session_id, sid)
        self.assertIs(window.timer._thread, worker)
        self.assertEqual(settings.load_settings()['daily_prompt'], 'Keep my prompt')

    def test_failed_mode_or_path_save_leaves_running_session_intact(self):
        window = self.window(expert=True)
        window.basic_panel._toggle()
        sid = window.timer.session_id
        with patch('app.qt_window.save_settings', return_value=False), patch('app.qt_window.QMessageBox.warning') as warning:
            window.title_bar.mode_button.click()
            self.assertEqual(window.experience_mode, 'expert')
            window.basic_panel.course_path_checkbox.setChecked(False)
            self.assertTrue(window.basic_panel.course_path_checkbox.isChecked())
            self.assertEqual(warning.call_count, 2)
        self.assertEqual(window.timer.session_id, sid)
        self.assertTrue(window.timer.is_running)

    def test_checkbox_persists_and_schedule_start_requires_an_unfinished_task(self):
        window = self.window(expert=True)
        panel = window.basic_panel
        self.assertTrue(panel.course_path_checkbox.isChecked())
        panel.course_path_checkbox.setChecked(False)
        self.assertFalse(settings.load_settings()['expert_course_path'])
        self.assertTrue(panel.course_row.isHidden())
        self.assertFalse(panel.schedule_context.isHidden())
        self.assertFalse(panel.start_btn.isEnabled())
        panel._toggle()
        self.assertIsNone(window.timer.session_id)
        self.routine()
        window._load_active_schedule()
        self.assertTrue(panel.start_btn.isEnabled())
        window.title_bar.mode_button.click()
        self.assertTrue(panel.path_row.isHidden())
        window.title_bar.mode_button.click()
        self.assertFalse(panel.course_path_checkbox.isChecked())

    def test_schedule_completes_at_focus_end_turns_green_and_advances_once(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(20)
        panel._toggle()
        target = window.timer.focus_context
        focus_sid = window.timer.session_id
        with window.timer._condition:
            window.timer._deadline -= 660
        window.timer.pause()
        self.app.processEvents()
        self.assertFalse(storage.get_schedule_tasks(sid)[0].get('completed'))
        self.assertEqual(storage.get_schedule_position(sid), 0)
        panel._toggle()
        self.finish(window)
        self.assertTrue(storage.get_schedule_tasks(sid)[0]['completed'])
        self.assertFalse(storage.get_schedule_tasks(sid)[1].get('completed'))
        self.assertEqual(storage.get_schedule_position(sid), 1)
        brush = window.table_model.data(window.table_model.index(0, 1), Qt.ItemDataRole.ForegroundRole)
        self.assertEqual(brush.color().name(), '#59d5ae')
        self.assertEqual(window.completed_value.text(), '1')
        window._on_focus_completed(focus_sid, target)
        self.assertEqual(stats.get_stats_summary()['tasks_completed'], 1)
        self.assertEqual(storage.get_schedule_position(sid), 1)
        self.assertEqual(stats.course_totals(stats.get_courses()[self.cid])['study_seconds'], 0)

    def test_expert_course_path_records_course_hours_without_completing_schedule(self):
        sid = self.routine()
        window = self.window(expert=True)
        window.basic_panel.minutes.setValue(20)
        window.basic_panel._toggle()
        self.assertIsNone(window.timer.focus_context)
        self.finish(window)
        window.timer.shutdown()
        self.assertFalse(storage.get_schedule_tasks(sid)[0].get('completed'))
        self.assertEqual(stats.course_totals(stats.get_courses()[self.cid])['study_seconds'], 1200)
        self.assertEqual(stats.get_stats_summary()['tasks_completed'], 0)

    def test_changing_path_saves_partial_course_time_and_binds_new_schedule_session(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel._toggle()
        old_sid = window.timer.session_id
        with window.timer._condition:
            window.timer._deadline -= 12
        panel.course_path_checkbox.setChecked(False)
        self.assertEqual(window.timer.state, State.IDLE)
        self.assertIsNone(window.timer.course_id)
        panel.minutes.setValue(1)
        panel._toggle()
        self.assertNotEqual(window.timer.session_id, old_sid)
        self.finish(window)
        window.timer.shutdown()
        self.assertTrue(storage.get_schedule_tasks(sid)[0]['completed'])
        self.assertEqual(stats.course_totals(stats.get_courses()[self.cid])['study_seconds'], 12)
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 72)

    def test_changing_to_course_does_not_complete_partially_studied_schedule_task(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel._toggle()
        with window.timer._condition:
            window.timer._deadline -= 10
        panel.course_path_checkbox.setChecked(True)
        panel.minutes.setValue(1)
        panel._toggle()
        self.finish(window)
        window.timer.shutdown()
        self.assertFalse(storage.get_schedule_tasks(sid)[0].get('completed'))
        self.assertEqual(stats.course_totals(stats.get_courses()[self.cid])['study_seconds'], 60)
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 70)

    def test_schedule_binding_survives_quick_switch_to_basic(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        focus_sid = window.timer.session_id
        window.title_bar.mode_button.click()
        self.assertEqual(window.experience_mode, 'basic')
        self.assertEqual(window.timer.session_id, focus_sid)
        self.assertFalse(window.uses_course_path)
        self.finish(window)
        self.assertTrue(storage.get_schedule_tasks(sid)[0]['completed'])
        panel._stop()
        self.assertTrue(window.uses_course_path)
        panel._toggle()
        self.assertIsNone(window.timer.focus_context)

    def test_weekly_day_change_does_not_redirect_completion(self):
        sid = self.routine(weekly=True)
        window = self.window(expert=True)
        window.day_selector.setCurrentText('Monday')
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        window.day_selector.setCurrentText('Tuesday')
        self.finish(window)
        self.assertTrue(storage.get_schedule_tasks(sid, 'Monday')[0]['completed'])
        self.assertFalse(storage.get_schedule_tasks(sid, 'Tuesday')[0].get('completed'))
        self.assertEqual(window.completed_value.text(), '0')

    def test_changing_active_routine_does_not_redirect_completion(self):
        first = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        other = storage.create_daily_schedule('Other routine', [{'text': 'Keep this task'}])
        storage.set_active_schedule(other)
        window._load_active_schedule()
        self.finish(window)
        self.assertTrue(storage.get_schedule_tasks(first)[0]['completed'])
        self.assertFalse(storage.get_schedule_tasks(other)[0].get('completed'))

    def test_editing_and_moving_timed_task_preserves_its_identity(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        tasks = storage.get_schedule_tasks(sid)
        editor = SingleTaskDialog(task=tasks[0])
        self.addCleanup(editor.deleteLater)
        editor.entry_name.setText('Renamed timed task')
        editor._save()
        self.assertEqual(editor.result_task['_decipline_task_id'], window.timer.focus_context['task_id'])
        storage.save_schedule_tasks(sid, [tasks[1], editor.result_task], active_index=1)
        self.finish(window)
        saved = storage.get_schedule_tasks(sid)
        self.assertFalse(saved[0].get('completed'))
        self.assertTrue(saved[1]['completed'])
        self.assertEqual(saved[1]['text'], 'Renamed timed task')

    def test_deleted_target_never_completes_replacement_task(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        tasks = storage.get_schedule_tasks(sid)
        storage.save_schedule_tasks(sid, tasks[1:])
        self.finish(window)
        self.assertFalse(storage.get_schedule_tasks(sid)[0].get('completed'))
        self.assertEqual(stats.get_stats_summary()['tasks_completed'], 0)

    def test_manual_completion_during_focus_does_not_complete_next_task_twice(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        window._mark_active_task_complete()
        self.finish(window)
        self.assertTrue(storage.get_schedule_tasks(sid)[0]['completed'])
        self.assertFalse(storage.get_schedule_tasks(sid)[1].get('completed'))
        self.assertEqual(storage.get_schedule_position(sid), 1)
        self.assertEqual(stats.get_stats_summary()['tasks_completed'], 1)

    def test_last_scheduled_task_allows_break_then_disables_empty_focus(self):
        sid = storage.create_daily_schedule('Single task', [{'text': 'Only task'}])
        storage.set_active_schedule(sid)
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        self.finish(window)
        self.assertTrue(panel.start_btn.isEnabled())
        self.assertEqual(panel.start_btn.text(), 'Start break')
        panel._toggle()
        with window.timer._condition:
            window.timer._update(window.timer._deadline)
        self.app.processEvents()
        self.assertFalse(panel.start_btn.isEnabled())
        self.assertFalse(window.schedule_focus_available)

    def test_queued_completion_still_uses_original_target_after_checkbox_change(self):
        sid = self.routine()
        window = self.window(expert=True)
        window.timer._wake_worker = Mock()
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        def finish_in_worker():
            with window.timer._condition:
                window.timer._update(window.timer._deadline)
        thread = threading.Thread(target=finish_in_worker)
        thread.start()
        thread.join()
        panel.course_path_checkbox.setChecked(True)
        self.app.processEvents()
        self.assertTrue(storage.get_schedule_tasks(sid)[0]['completed'])
        self.assertFalse(storage.get_schedule_tasks(sid)[1].get('completed'))
        window.timer.shutdown()
        window.timer._run()

    def test_early_break_preserves_task_target_and_only_focus_completion_marks_it(self):
        sid = self.routine()
        window = self.window(expert=True)
        panel = window.basic_panel
        panel.course_path_checkbox.setChecked(False)
        panel.minutes.setValue(1)
        panel._toggle()
        target = window.timer.focus_context
        with window.timer._condition:
            window.timer._deadline -= 10
            panel._break()
            window.timer._deadline -= 5
            panel._break()
        self.assertEqual(window.timer.state, State.PAUSED)
        self.assertEqual(window.timer.focus_context, target)
        self.assertFalse(storage.get_schedule_tasks(sid)[0].get('completed'))
        panel._toggle()
        self.finish(window)
        self.assertTrue(storage.get_schedule_tasks(sid)[0]['completed'])
        window.timer.shutdown()
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 60)
        self.assertEqual(stats.get_stats_summary()['break_seconds'], 5)


class NotificationTests(unittest.TestCase):
    setUpClass = classmethod(TrackingPathTests.setUpClass.__func__)
    setUp = TrackingPathTests.setUp
    window = TrackingPathTests.window
    finish = TrackingPathTests.finish

    def completion(self, cycle=1):
        window = self.window()
        window._show_focus_completion = MainWindow._show_focus_completion.__get__(window)
        window._play_notification_sound = Mock()
        window.timer.select_cycle(cycle - 1)
        window.basic_panel.minutes.setValue(1)
        window.basic_panel._toggle()
        return window

    def test_focus_popup_waits_for_ok_and_restores_hidden_window(self):
        from PyQt6.QtWidgets import QDialogButtonBox
        window = self.completion()
        window.hide_to_tray()
        with patch('app.telegram_bot.notify_async') as telegram:
            self.finish(window)
            popup = window._focus_done_popup
            self.assertTrue(window.isVisible())
            self.assertTrue(popup.isVisible())
            self.assertEqual(window.timer.state, State.WAITING_FOR_BREAK)
            self.assertIsNone(window.timer._deadline)
            window._on_work_done()
            self.assertIs(window._focus_done_popup, popup)
            popup.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
            self.assertEqual(window.timer.state, State.SHORT_BREAK)
            self.assertTrue(window.timer.is_running)
            self.assertGreater(window.timer.remaining, settings.load_settings()['short_break'] * 60 - 2)
            self.assertIsNone(window._focus_done_popup)
            telegram.assert_not_called()

    def test_fourth_cycle_ok_starts_full_long_break(self):
        window = self.completion(4)
        self.finish(window)
        window._focus_done_popup.accept()
        self.assertEqual(window.timer.state, State.LONG_BREAK)
        self.assertGreater(window.timer.remaining, settings.load_settings()['long_break'] * 60 - 2)

    def test_closing_popup_does_not_start_break(self):
        window = self.completion()
        self.finish(window)
        window._focus_done_popup.close()
        self.assertIsNone(window._focus_done_popup)
        self.assertEqual(window.timer.state, State.WAITING_FOR_BREAK)
        self.assertFalse(window.timer.is_running)
        window.basic_panel._toggle()
        self.assertEqual(window.timer.state, State.SHORT_BREAK)

    def test_reset_dismisses_popup_and_stale_ok_cannot_start_new_session_break(self):
        window = self.completion()
        self.finish(window)
        old_popup = window._focus_done_popup
        window.timer.reset()
        self.assertIsNone(window._focus_done_popup)
        window.basic_panel._toggle()
        # Complete synchronously so the old dialog is still alive until Qt deletes it.
        with window.timer._condition:
            window.timer._update(window.timer._deadline)
        new_popup = window._focus_done_popup
        old_popup.accept()
        self.assertEqual(window.timer.state, State.WAITING_FOR_BREAK)
        self.assertIs(window._focus_done_popup, new_popup)
        new_popup.reject()

    def test_only_natural_break_completion_sends_telegram(self):
        window = self.completion()
        with patch('app.telegram_bot.notify_async') as telegram:
            self.finish(window)
            window._focus_done_popup.accept()
            self.finish(window)
            telegram.assert_called_once_with('Break complete: Ready for your next focus session.')
            with patch('app.qt_window.show_notification') as local_notice:
                window._notify_phase = MainWindow._notify_phase.__get__(window)
                window._on_free_done()
                local_notice.assert_called_once_with('Timer complete', 'Your timer has finished.')
            self.assertEqual(telegram.call_count, 1)

    def test_ending_break_early_does_not_send_telegram(self):
        window = self.completion()
        with patch('app.telegram_bot.notify_async') as telegram:
            self.finish(window)
            window._focus_done_popup.accept()
            window.timer.end_break()
            self.app.processEvents()
            telegram.assert_not_called()


if __name__ == '__main__':
    unittest.main()
