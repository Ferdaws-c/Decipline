"""
notifier.py - PyQt6 Toast Notifications.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QApplication, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from .qt_style import *

class BreakPopup(QDialog):
    def __init__(self, parent, on_ok_callback, is_long_break=False):
        super().__init__(parent)
        self.on_ok_callback = on_ok_callback
        
        self.setWindowTitle("Decipline")
        self.setFixedSize(360, 280)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 16px; }}")
        layout.addWidget(frame)
        
        flayout = QVBoxLayout(frame)
        flayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        emoji = QLabel("🎉" if is_long_break else "🧘")
        emoji.setFont(QFont(FONT_UI, 42))
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flayout.addWidget(emoji)
        
        title = QLabel("Great session! Long break time." if is_long_break else "Time for a break!")
        title.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flayout.addWidget(title)
        
        sub = QLabel(f"Step away for {'30' if is_long_break else '5'} minutes — you've earned it.")
        sub.setFont(QFont(FONT_UI, 12))
        sub.setStyleSheet(f"color: {TXT_SEC};")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flayout.addWidget(sub)
        
        btn = QPushButton("Start Break →")
        btn.setObjectName("PrimaryButton")
        btn.setFixedSize(180, 42)
        btn.clicked.connect(self._on_ok)
        
        btn_lyt = QHBoxLayout()
        btn_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_lyt.addWidget(btn)
        flayout.addLayout(btn_lyt)
        
        QTimer.singleShot(60000, self._on_ok)
        
    def _on_ok(self):
        if self.on_ok_callback:
            self.on_ok_callback()
        self.accept()


class AlarmDonePopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Decipline")
        self.setFixedSize(320, 230)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 14px; }}")
        layout.addWidget(frame)
        
        flayout = QVBoxLayout(frame)
        flayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        emoji = QLabel("⏰")
        emoji.setFont(QFont(FONT_UI, 36))
        emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flayout.addWidget(emoji)
        
        title = QLabel("Break's over — back to work!")
        title.setFont(QFont(FONT_UI, 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flayout.addWidget(title)
        
        btn = QPushButton("Let's Go!")
        btn.setObjectName("PrimaryButton")
        btn.setFixedSize(130, 36)
        btn.clicked.connect(self.accept)
        
        btn_lyt = QHBoxLayout()
        btn_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_lyt.addWidget(btn)
        flayout.addLayout(btn_lyt)
        
        QTimer.singleShot(15000, self.accept)


def show_notification(title, message):
    """Use the application's native Windows tray notification without blocking."""
    app = QApplication.instance()
    if app is None or not QSystemTrayIcon.supportsMessages():
        return False
    for tray in app.findChildren(QSystemTrayIcon):
        if tray.isVisible():
            tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 6000)
            return True
    return False
