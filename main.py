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
            hwnd = user32.FindWindowW(None, "MainWindowWindow") # PyQt class name usually
            if hwnd:
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return False, None

def main():
    multiprocessing.freeze_support()
    is_single, lock_socket = _acquire_single_instance()
    if not is_single:
        sys.exit(0)

    app = QApplication(sys.argv)
    apply_global_style(app)
    
    # Needs to be set to prevent app closing when main window is hidden
    app.setQuitOnLastWindowClosed(False)

    from app.qt_window import MainWindow
    window = MainWindow()
    
    # System Tray
    tray_icon = QSystemTrayIcon(QIcon(_asset("icon.ico")), app)
    
    menu = QMenu()
    action_open = QAction("Open Decipline")
    action_open.triggered.connect(window.showNormal)
    menu.addAction(action_open)
    
    menu.addSeparator()
    
    action_quit = QAction("Quit")
    action_quit.triggered.connect(app.quit)
    menu.addAction(action_quit)
    
    tray_icon.setContextMenu(menu)
    tray_icon.activated.connect(
        lambda reason: window.showNormal() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None
    )
    tray_icon.show()
    
    window.show()

    ret = app.exec()

    if lock_socket:
        try: lock_socket.close()
        except: pass
        
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


