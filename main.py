"""
main.py — Decipline entry point.

Starts the system tray icon and main window.
Enforces a single running instance across the system.
"""

import sys
import os
import socket
import multiprocessing
import ctypes
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from app.qt_style import apply_global_style

def _asset(name: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", name)

def _acquire_single_instance(port: int = 52187):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        return True, s
    except socket.error:
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, "Decipline")
            if hwnd:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return False, None

def main():
    multiprocessing.freeze_support()
    # A packaged smoke check gets isolated data and can run beside the real app.
    smoke_test = "--smoke-test" in sys.argv
    smoke_directory = None
    if smoke_test:
        import tempfile
        smoke_directory = tempfile.TemporaryDirectory(prefix="decipline-smoke-")
        os.environ["DECIPLINE_DATA_DIR"] = smoke_directory.name
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        is_single, lock_socket = True, None
    else:
        is_single, lock_socket = _acquire_single_instance()
    if not is_single:
        sys.exit(0)

    app = QApplication(sys.argv)
    apply_global_style(app)
    
    # Needs to be set to prevent app closing when main window is hidden
    app.setQuitOnLastWindowClosed(False)

    from app.settings import load_settings
    if not smoke_test and not load_settings().get("onboarding_completed", False):
        from app.qt_setup import SetupDialog
        setup = SetupDialog()
        if not setup.exec():
            if lock_socket:
                lock_socket.close()
            sys.exit(0)
        setup.deleteLater()

    from app.stats import recover_lecture_sessions
    recover_lecture_sessions()
    from app.qt_window import MainWindow
    window = MainWindow()
    app.aboutToQuit.connect(window.timer.shutdown)
    
    # System Tray
    tray_icon = QSystemTrayIcon(QIcon(_asset("icon.ico")), app)
    tray_icon.setToolTip("Decipline · click to open")
    
    menu = QMenu()
    action_open = QAction("Open Decipline")
    action_open.triggered.connect(window.restore_from_tray)
    menu.addAction(action_open)
    
    menu.addSeparator()
    
    action_quit = QAction("Close app")
    action_quit.triggered.connect(window.close_app)
    menu.addAction(action_quit)
    
    tray_icon.setContextMenu(menu)
    tray_icon.activated.connect(
        lambda reason: window.restore_from_tray() if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ) else None
    )
    tray_icon.show()
    
    window.show()

    if smoke_test:
        window._notify_phase = lambda *args: None
        from PyQt6.QtCore import QTimer
        from app.qt_trends import TrendsDialog
        from app import stats, storage
        from app.qt_prompt_editor import PromptEditorDialog
        cid = stats.create_course("Smoke test course")
        lid = stats.create_lecture(cid, "Smoke test lecture")
        basic = window.basic_panel
        basic.reload_courses(cid, lid)
        basic.minutes.setValue(1)
        basic.cycles.buttons[3].click()
        basic._toggle()
        session_id = window.timer.session_id
        window.title_bar.hide_button.click()
        assert not window.isVisible() and window.timer.is_running
        window.restore_from_tray()
        assert window.isVisible() and window.timer.session_id == session_id
        with window.timer._condition:
            window.timer._deadline -= 60
        basic._toggle()
        basic._toggle()
        basic._stop()
        scheduled = storage.create_daily_schedule("Schedule path smoke", [
            {"text": "Finish this task", "duration": 1}, {"text": "Keep next task", "duration": 1}])
        storage.set_active_schedule(scheduled)
        window._load_active_schedule()
        window.title_bar.mode_button.click()
        assert window.experience_mode == "expert"
        basic.course_path_checkbox.setChecked(False)
        basic._toggle()
        schedule_session = window.timer.session_id
        window.title_bar.mode_button.click()
        assert window.experience_mode == "basic" and window.timer.session_id == schedule_session
        with window.timer._condition:
            window.timer._deadline -= 60
        basic._toggle()
        assert storage.get_schedule_tasks(scheduled)[0]["completed"]
        assert not storage.get_schedule_tasks(scheduled)[1].get("completed")
        basic._stop()
        window.title_bar.mode_button.click()
        assert not basic.course_path_checkbox.isChecked()
        window.timer.shutdown()
        summary = stats.get_stats_summary()
        assert summary["study_seconds"] == 120
        assert stats.course_totals(summary["courses"][cid])["study_seconds"] == 60
        from app.qt_courses import CourseManagerDialog
        manager = CourseManagerDialog(window, cid, lid)
        manager.show()
        manager.grab()
        stats.rename_course(cid, "Renamed smoke course")
        stats.rename_lecture(cid, lid, "Renamed smoke lecture")
        stats.delete_lecture(cid, lid)
        assert lid not in stats.get_courses()[cid]["lectures"]
        assert stats.course_totals(stats.get_courses()[cid])["study_seconds"] == 60
        manager.show_removed.setChecked(True)
        stats.restore_lecture(cid, lid)
        stats.delete_course(cid)
        assert cid not in stats.get_courses()
        stats.restore_course(cid)
        manager.reload(cid, lid)
        manager.close()
        manager.deleteLater()
        basic.reload_courses(cid, lid)
        routine = storage.create_daily_schedule("CRUD smoke routine", [{"text": "Draft task"}])
        storage.rename_schedule(routine, "Renamed smoke routine")
        storage.save_schedule_tasks(routine, [{"text": "Edited task", "duration": 25}])
        assert storage.get_schedule_tasks(routine)[0]["text"] == "Edited task"
        storage.delete_schedule(routine)
        assert storage.get_schedule_by_id(routine) is None
        trends = TrendsDialog(window)
        for index in range(trends.range_combo.count()):
            trends.range_combo.setCurrentIndex(index)
            trends.chart.grab()
        trends.course_combo.setCurrentIndex(1)
        trends.deleteLater()
        prompts = PromptEditorDialog(window)
        prompts.daily.setPlainText("Smoke test daily JSON prompt")
        prompts.save()
        prompts.deleteLater()
        from app.qt_setup import SetupDialog
        setup = SetupDialog(window)
        setup.save_choice()
        setup.deleteLater()
        window.apply_experience_mode()
        QTimer.singleShot(250, app.quit)

    ret = app.exec()

    if lock_socket:
        try: lock_socket.close()
        except: pass
    if smoke_directory:
        smoke_directory.cleanup()
        
    sys.exit(ret)

def global_exception_handler(exc_type, exc_value, exc_traceback):
    import traceback
    with open("crash.log", "a", encoding="utf-8") as f:
        f.write("Unhandled Exception:\\n")
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
        f.write("\\n")

sys.excepthook = global_exception_handler

if __name__ == "__main__":
    main()


