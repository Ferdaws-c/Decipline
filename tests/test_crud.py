"""CRUD persistence, history preservation, active-session protection and UI flows."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox
from app import stats, storage, settings
from app.analytics import evaluate
from app.qt_courses import CourseManagerDialog
from app.qt_window import MainWindow
from app.qt_library import LibraryDialog
from app.qt_task_editor import TaskEditorDialog, SingleTaskDialog


class CrudTests(unittest.TestCase):
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

    def seed(self):
        cid = stats.create_course('Biology')
        lid = stats.create_lecture(cid, 'Cells')
        sid = stats.start_lecture_session(cid, lid)
        stats.add_lecture_time(sid, 120, 30)
        stats.finish_lecture_session(sid)
        return cid, lid, sid

    def test_rename_preserves_ids_history_and_totals_after_reopening(self):
        cid, lid, sid = self.seed()
        stats.rename_course(cid, 'Life sciences')
        stats.rename_lecture(cid, lid, 'Cell biology')
        stats._stats = None
        data = stats.get_stats_summary()
        self.assertEqual(data['courses'][cid]['name'], 'Life sciences')
        self.assertEqual(data['courses'][cid]['lectures'][lid]['name'], 'Cell biology')
        self.assertEqual(data['lecture_sessions'][sid]['lecture_id'], lid)
        self.assertEqual(data['study_seconds'], 120)
        self.assertEqual(data['break_seconds'], 30)
        self.assertEqual(len(data['courses']), 1)
        self.assertEqual(evaluate(data, None)['courses'][0][1]['name'], 'Life sciences')

    def test_remove_lecture_preserves_course_hours_and_restores_same_record(self):
        cid, lid, sid = self.seed()
        stats.delete_lecture(cid, lid)
        self.assertNotIn(lid, stats.get_courses()[cid]['lectures'])
        self.assertEqual(stats.course_totals(stats.get_courses()[cid])['study_seconds'], 120)
        result = evaluate(stats.get_stats_summary(), None, cid)
        self.assertEqual(result['lectures'][0][1]['name'], 'Cells (removed)')
        self.assertEqual(result['study_seconds'], 120)
        stats.restore_lecture(cid, lid)
        self.assertIn(lid, stats.get_courses()[cid]['lectures'])
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 120)
        self.assertEqual(len(stats.get_stats_summary()['lecture_sessions']), 1)

    def test_remove_course_preserves_history_and_child_removals(self):
        cid, lid, sid = self.seed()
        hidden = stats.create_lecture(cid, 'Old lecture')
        stats.delete_lecture(cid, hidden)
        stats.delete_course(cid)
        self.assertNotIn(cid, stats.get_courses())
        self.assertIn(cid, stats.get_courses(include_removed=True))
        data = stats.get_stats_summary()
        self.assertIn(sid, data['lecture_sessions'])
        self.assertEqual(evaluate(data, None)['courses'][0][1]['name'], 'Biology (removed)')
        stats.restore_course(cid)
        self.assertIn(lid, stats.get_courses()[cid]['lectures'])
        self.assertNotIn(hidden, stats.get_courses()[cid]['lectures'])
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 120)

    def test_removing_unused_items_keeps_trends_clear(self):
        cid = stats.create_course('Added by mistake')
        stats.delete_course(cid)
        self.assertEqual(evaluate(stats.get_stats_summary(), None)['courses'], [])
        from app.qt_trends import TrendsDialog
        dialog = TrendsDialog()
        self.addCleanup(dialog.deleteLater)
        self.assertEqual(dialog.course_combo.count(), 1)

    def test_adding_removed_name_restores_instead_of_duplicating_history(self):
        cid, lid, sid = self.seed()
        stats.delete_lecture(cid, lid)
        self.assertEqual(stats.create_lecture(cid, ' cells '), lid)
        stats.delete_course(cid)
        self.assertEqual(stats.create_course(' BIOLOGY '), cid)
        self.assertEqual(len(stats.get_courses()), 1)
        self.assertEqual(stats.course_totals(stats.get_courses()[cid])['study_seconds'], 120)

    def test_blank_and_duplicate_renames_do_not_change_saved_records(self):
        cid, lid, sid = self.seed()
        other = stats.create_course('Physics')
        other_lid = stats.create_lecture(cid, 'Genetics')
        before = (self.base / 'stats.json').read_bytes()
        for action in (lambda: stats.rename_course(cid, ' '), lambda: stats.rename_course(cid, 'physics'),
                       lambda: stats.rename_lecture(cid, lid, '\t'), lambda: stats.rename_lecture(cid, lid, 'GENETICS')):
            with self.assertRaises(ValueError):
                action()
        self.assertEqual((self.base / 'stats.json').read_bytes(), before)
        self.assertEqual(stats.get_courses()[cid]['name'], 'Biology')

    def test_failed_metadata_save_rolls_back_names_but_keeps_buffered_study(self):
        cid, lid, sid = self.seed()
        before = (self.base / 'stats.json').read_bytes()
        stats.add_study_time(3)
        with patch('app.stats.os.replace', side_effect=OSError('disk busy')):
            with self.assertLogs('app.stats', level='ERROR'):
                with self.assertRaises(OSError):
                    stats.rename_course(cid, 'Unsaved name')
        self.assertEqual(stats.get_courses()[cid]['name'], 'Biology')
        self.assertEqual((self.base / 'stats.json').read_bytes(), before)
        stats.flush_stats()
        stats._stats = None
        self.assertEqual(stats.get_stats_summary()['study_seconds'], 123)

    def test_manager_buttons_support_full_course_and_lecture_crud_and_cancel(self):
        dialog = CourseManagerDialog()
        self.addCleanup(dialog.deleteLater)
        with patch('app.qt_courses.QInputDialog.getText', return_value=('Physics', True)):
            dialog.add_course_btn.click()
        cid = dialog.course.currentData()
        with patch('app.qt_courses.QInputDialog.getText', return_value=('Motion', True)):
            dialog.add_lecture_btn.click()
        lid = dialog._lecture_id()
        with patch('app.qt_courses.QInputDialog.getText', return_value=('Mechanics', True)):
            dialog.rename_course_btn.click()
        with patch('app.qt_courses.QInputDialog.getText', return_value=('Oscillations', True)):
            dialog.rename_lecture_btn.click()
        self.assertEqual(stats.get_courses()[cid]['name'], 'Mechanics')
        self.assertEqual(stats.get_courses()[cid]['lectures'][lid]['name'], 'Oscillations')
        with patch('app.qt_courses.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
            dialog.remove_lecture_btn.click()
        self.assertIn(lid, stats.get_courses()[cid]['lectures'])
        with patch('app.qt_courses.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            dialog.remove_lecture_btn.click()
        self.assertNotIn(lid, stats.get_courses()[cid]['lectures'])
        dialog.show_removed.setChecked(True)
        dialog.restore_lecture_btn.click()
        self.assertIn(lid, stats.get_courses()[cid]['lectures'])
        with patch('app.qt_courses.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            dialog.remove_course_btn.click()
        self.assertNotIn(cid, stats.get_courses())
        dialog.restore_course_btn.click()
        self.assertIn(cid, stats.get_courses())
        self.assertIn(lid, stats.get_courses()[cid]['lectures'])

    def test_manager_protects_active_selection_and_allows_rename_without_reset(self):
        cid, lid, _ = self.seed()
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.timer.shutdown)
        window.basic_panel.reload_courses(cid, lid)
        window.basic_panel._toggle()
        sid = window.timer.session_id
        dialog = CourseManagerDialog(window.basic_panel, cid, lid, (cid, lid))
        self.addCleanup(dialog.deleteLater)
        self.assertFalse(dialog.remove_course_btn.isEnabled())
        self.assertFalse(dialog.remove_lecture_btn.isEnabled())
        with patch('app.qt_courses.QMessageBox.question') as question:
            dialog._remove_course()
            dialog._remove_lecture()
            question.assert_not_called()
        with patch('app.qt_courses.QInputDialog.getText', return_value=('Life sciences', True)):
            dialog.rename_course_btn.click()
        window.basic_panel.reload_courses()
        self.assertEqual(window.basic_panel.course.currentText(), 'Life sciences')
        self.assertEqual(window.basic_panel.lecture.currentData(), lid)
        self.assertTrue(window.timer.is_running)
        self.assertEqual(window.timer.session_id, sid)

    def test_queued_progress_cannot_undo_renames_or_resurrect_removed_items(self):
        cid, lid, _ = self.seed()
        window = MainWindow()
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.timer.shutdown)
        panel = window.basic_panel
        panel.reload_courses(cid, lid)
        old = stats.get_courses()
        stats.rename_course(cid, 'Life sciences')
        stats.delete_lecture(cid, lid)
        panel.reload_courses()
        panel._stats_updated(old)
        self.assertEqual(panel._courses[cid]['name'], 'Life sciences')
        self.assertNotIn(lid, panel._courses[cid]['lectures'])
        self.assertEqual(stats.course_totals(panel._courses[cid])['study_seconds'], 120)
        stats.delete_course(cid)
        panel.reload_courses()
        panel._stats_updated(old)
        self.assertNotIn(cid, panel._courses)
        self.assertIsNone(window.timer.course_id)

    def test_daily_and_weekly_task_crud_preserves_other_days_and_active_task(self):
        for kind in ('daily', 'weekly'):
            with self.subTest(kind=kind):
                tasks = [{'text': name, 'duration': 25, 'completed': name == 'A'} for name in ('A', 'B', 'C')]
                sid = (storage.create_daily_schedule('Routine', tasks) if kind == 'daily' else
                       storage.create_weekly_schedule('Routine', {'Monday': tasks, 'Tuesday': [{'text': 'Keep Tuesday'}]}))
                storage.set_active_schedule(sid)
                day = 'Monday' if kind == 'weekly' else None
                storage.set_active_task_index(1, day)
                editor = TaskEditorDialog(sid=sid, schedule_type=kind)
                self.addCleanup(editor.deleteLater)
                def submitted(parent, task=None):
                    dialog = SingleTaskDialog(parent, task)
                    dialog.entry_name.setText('A updated' if task else 'D')
                    dialog.entry_notes.setText('Saved note')
                    dialog._save()
                    dialog.exec = lambda: 1
                    return dialog
                with patch('app.qt_task_editor.SingleTaskDialog', side_effect=submitted):
                    editor._add_task()
                    editor.table.selectRow(0)
                    editor._edit_task()
                saved = storage.get_schedule_tasks(sid, day)
                self.assertEqual([t['text'] for t in saved], ['A updated', 'B', 'C', 'D'])
                self.assertTrue(saved[0]['completed'])
                self.assertEqual(saved[0]['notes'], 'Saved note')
                editor.table.selectRow(1)
                editor._move_down()
                self.assertEqual(storage.get_schedule_position(sid, day), 2)
                editor._move_up()
                self.assertEqual(storage.get_schedule_position(sid, day), 1)
                editor.table.selectRow(0)
                with patch('app.qt_task_editor.QMessageBox.exec', return_value=QMessageBox.StandardButton.No):
                    editor._delete_task()
                self.assertEqual(len(storage.get_schedule_tasks(sid, day)), 4)
                with patch('app.qt_task_editor.QMessageBox.exec', return_value=QMessageBox.StandardButton.Yes):
                    editor._delete_task()
                self.assertEqual(storage.get_schedule_position(sid, day), 0)
                self.assertEqual(storage.get_schedule_tasks(sid, day)[0]['text'], 'B')
                if kind == 'weekly':
                    self.assertEqual(storage.get_schedule_tasks(sid, 'Tuesday'), [{'text': 'Keep Tuesday'}])

    def test_schedule_library_crud_and_cancel_for_daily_and_weekly(self):
        library = LibraryDialog()
        self.addCleanup(library.deleteLater)
        for kind in ('daily', 'weekly'):
            library._switch_tab(kind)
            with patch('app.qt_library.QInputDialog.getText', return_value=('My routine', True)):
                library._create_new()
            library.list_widget.setCurrentRow(0)
            sid = library._get_selected_id()
            storage.set_active_schedule(sid)
            with patch('app.qt_library.QInputDialog.getText', return_value=('Updated routine', True)):
                library._rename_selected()
            self.assertEqual(storage.get_schedule_by_id(sid)['name'], 'Updated routine')
            library.list_widget.setCurrentRow(0)
            with patch('app.qt_library.QMessageBox.exec', return_value=QMessageBox.StandardButton.No):
                library._delete_selected()
            self.assertIsNotNone(storage.get_schedule_by_id(sid))
            with patch('app.qt_library.QMessageBox.exec', return_value=QMessageBox.StandardButton.Yes):
                library._delete_selected()
            self.assertIsNone(storage.get_schedule_by_id(sid))
            self.assertEqual(library.list_widget.count(), 0)

    def test_failed_schedule_and_task_saves_preserve_existing_library(self):
        sid = storage.create_daily_schedule('Keep routine', [{'text': 'Keep task'}])
        before = (self.base / 'schedules.json').read_bytes()
        library = LibraryDialog()
        library.list_widget.setCurrentRow(0)
        editor = TaskEditorDialog(sid=sid)
        self.addCleanup(library.deleteLater)
        self.addCleanup(editor.deleteLater)
        with patch('app.storage.os.replace', side_effect=OSError('disk busy')), \
             patch('app.qt_library.QInputDialog.getText', return_value=('Unsaved', True)), \
             patch('app.qt_library.QMessageBox.warning') as warning:
            library._rename_selected()
            warning.assert_called_once()
        with patch('app.storage.os.replace', side_effect=OSError('disk busy')), \
             patch('app.qt_task_editor.QMessageBox.warning') as warning:
            self.assertFalse(editor._save_tasks([{'text': 'Unsaved task'}]))
            warning.assert_called_once()
        self.assertEqual((self.base / 'schedules.json').read_bytes(), before)
        self.assertEqual(storage.get_schedule_by_id(sid)['name'], 'Keep routine')
        self.assertEqual(storage.get_schedule_tasks(sid)[0]['text'], 'Keep task')


if __name__ == '__main__':
    unittest.main()
