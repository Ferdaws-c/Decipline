"""Render the current product with isolated sample data, never personal data."""
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timedelta
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    output = Path('build/ui-review-current').resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        os.environ['DECIPLINE_DATA_DIR'] = directory
        from PyQt6.QtGui import QFontDatabase
        from PyQt6.QtWidgets import QApplication
        from app import stats, storage, settings
        from app.qt_style import apply_global_style
        from app.qt_window import MainWindow
        from app.qt_trends import TrendsDialog
        from app.qt_library import LibraryDialog
        from app.qt_prompt_editor import PromptEditorDialog
        from app.qt_settings import SettingsDialog
        from app.qt_setup import SetupDialog
        from app.qt_courses import CourseManagerDialog
        app = QApplication([])
        for font in ('segoeui.ttf', 'segoeuib.ttf', 'seguiemj.ttf'):
            path = Path('C:/Windows/Fonts') / font
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
        apply_global_style(app)
        settings.save_settings({'experience_mode': 'basic', 'onboarding_completed': True, 'sound_enabled': False})
        captures = []
        def capture(widget, name):
            widget.show()
            app.processEvents()
            widget.grab().save(str(output / f'{name}.png'))
            captures.append(name)
        window = MainWindow()
        capture(window, 'basic-empty')
        trends = TrendsDialog(window)
        capture(trends, 'trends-empty')
        trends.close()
        trends.deleteLater()
        cid = stats.create_course('Biology')
        lid = stats.create_lecture(cid, 'Cell structure & function')
        other = stats.create_course('Mathematics')
        for i, values in enumerate(((1800, 300), (3600, 1500), (1500, 2700), (4500, 1800), (0, 0), (3000, 900), (1500, 2100))):
            for j, seconds in enumerate(values):
                if not seconds:
                    continue
                stamp = (datetime.now().replace(hour=10 + j, minute=0, second=0, microsecond=0) - timedelta(days=6 - i)).isoformat()
                sid = f'sample-{i}-{j}'
                stats.open_pomodoro_session(sid, cid if j == 0 else other, lid if j == 0 else None, 1, stamp)
                stats.add_lecture_time(sid, seconds, 300, stamp)
                stats.complete_pomodoro_session(sid, stamp)
                stats.close_pomodoro_session(sid, stamp)
        stats.flush_stats()
        panel = window.basic_panel
        panel.reload_courses(cid)
        capture(window, 'basic-course')
        panel.cycles.buttons[2].click()
        panel._toggle()
        with window.timer._condition:
            window.timer._deadline -= 94
        window.timer.pause()
        panel.sync()
        capture(window, 'basic-paused')
        panel._break()
        capture(window, 'basic-break')
        window.resize(400, 520)
        capture(window, 'basic-minimum')
        panel._stop()
        panel.reload_courses(cid, lid)
        window.resize(440, 570)
        capture(window, 'basic-lecture')
        tasks = [{'time': f'{9+i:02d}:00', 'text': text, 'duration': 25, 'notes': '', 'completed': i < 2}
                 for i, text in enumerate(('Set intentions', 'Read & review', 'Cell biology', 'Practice questions', 'Write study notes', 'Genetics lecture', 'Plan tomorrow'))]
        schedule = storage.create_daily_schedule('A little progress, every day.', tasks)
        storage.set_active_schedule(schedule)
        storage.set_active_task_index(2)
        window._load_active_schedule()
        saved = settings.load_settings()
        saved['experience_mode'] = 'expert'
        settings.save_settings(saved)
        window.apply_experience_mode()
        capture(window, 'expert')
        window.resize(980, 720)
        capture(window, 'expert-minimum')
        panel.course_path_checkbox.setChecked(False)
        window.resize(1160, 820)
        capture(window, 'expert-schedule')
        panel.minutes.setValue(1)
        panel._toggle()
        with window.timer._condition:
            window.timer._deadline -= 60
        window.timer.pause()
        panel.sync()
        app.processEvents()
        window.resize(980, 720)
        capture(window, 'expert-schedule-complete')
        panel._stop()
        for dialog, name in ((TrendsDialog(window), 'trends'), (SettingsDialog(window), 'settings'),
                             (LibraryDialog(window), 'library'), (PromptEditorDialog(window), 'prompts'), (SetupDialog(), 'setup'),
                             (CourseManagerDialog(window, cid, lid), 'manage-courses')):
            capture(dialog, name)
            if name == 'trends':
                for index in range(dialog.range_combo.count()):
                    dialog.range_combo.setCurrentIndex(index)
                    app.processEvents()
                dialog.range_combo.setCurrentIndex(1)
                dialog.course_combo.setCurrentIndex(1)
                capture(dialog, 'trends-course')
                dialog.resize(680, 620)
                capture(dialog, 'trends-minimum')
            if name == 'settings':
                dialog.telegram_help_btn.click()
                capture(dialog._telegram_help_dialog, 'telegram-setup-guide')
                dialog._telegram_help_dialog.accept()
            if name == 'manage-courses':
                unused = stats.create_course('Earlier course')
                stats.delete_course(unused)
                dialog.show_removed.setChecked(True)
                dialog.course.setCurrentIndex(dialog.course.findData(unused))
                capture(dialog, 'manage-removed')
            dialog.close()
            dialog.deleteLater()
        window.timer.shutdown()
        window.close()
        window.deleteLater()
        app.processEvents()
        print(f'Rendered {len(captures)} screens in {output}')


if __name__ == '__main__':
    main()
