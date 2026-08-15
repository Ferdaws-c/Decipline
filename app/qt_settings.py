"""
qt_settings.py - PyQt6 Settings Dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .qt_style import *
from .settings import load_settings, save_settings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(370, 540)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self.settings = load_settings()
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        
        lbl = QLabel("Settings")
        lbl.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        layout.addWidget(lbl)
        
        # Focus Time
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Focus Time (min):"))
        self.spin_focus = QSpinBox()
        self.spin_focus.setRange(1, 120)
        self.spin_focus.setValue(self.settings.get("focus_time", 25))
        row1.addWidget(self.spin_focus)
        layout.addLayout(row1)
        
        # Short Break
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Short Break (min):"))
        self.spin_short = QSpinBox()
        self.spin_short.setRange(1, 60)
        self.spin_short.setValue(self.settings.get("short_break", 5))
        row2.addWidget(self.spin_short)
        layout.addLayout(row2)
        
        # Long Break
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Long Break (min):"))
        self.spin_long = QSpinBox()
        self.spin_long.setRange(1, 120)
        self.spin_long.setValue(self.settings.get("long_break", 30))
        row3.addWidget(self.spin_long)
        layout.addLayout(row3)
        
        # Auto-Complete
        row_ac = QHBoxLayout()
        row_ac.addWidget(QLabel("Auto-Complete Task After (min):"))
        self.spin_autocomplete = QSpinBox()
        self.spin_autocomplete.setRange(1, self.spin_focus.value()) # dynamically bounded
        self.spin_autocomplete.setValue(min(self.settings.get("autocomplete_minutes", 10), self.spin_focus.value()))
        row_ac.addWidget(self.spin_autocomplete)
        layout.addLayout(row_ac)
        
        # Connect dynamic bounding
        self.spin_focus.valueChanged.connect(self._update_autocomplete_max)
        
        # Sound
        self.chk_sound = QCheckBox("Enable Alarm Sound")
        self.chk_sound.setChecked(self.settings.get("sound_enabled", True))
        layout.addWidget(self.chk_sound)
        
        from PyQt6.QtWidgets import QFrame, QLineEdit
        
        # Telegram Integration
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(line)
        
        lbl_tg = QLabel("Telegram Integration")
        lbl_tg.setFont(QFont(FONT_UI, 12, QFont.Weight.Bold))
        layout.addWidget(lbl_tg)
        
        self.chk_tg = QCheckBox("Enable Telegram Notifications")
        self.chk_tg.setChecked(self.settings.get("telegram_enabled", False))
        layout.addWidget(self.chk_tg)
        
        layout.addWidget(QLabel("Bot Token (from @BotFather):"))
        self.entry_token = QLineEdit(self.settings.get("telegram_token", ""))
        self.entry_token.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        layout.addWidget(self.entry_token)
        
        layout.addWidget(QLabel("Your Chat ID (from @userinfobot):"))
        self.entry_chat_id = QLineEdit(self.settings.get("telegram_chat_id", ""))
        layout.addWidget(self.entry_chat_id)
        
        btn_test_tg = QPushButton("Test Connection")
        btn_test_tg.clicked.connect(self._test_telegram)
        layout.addWidget(btn_test_tg)
        
        layout.addStretch()
        
        # Buttons
        ctrl = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        ctrl.addWidget(btn_cancel)
        
        btn_save = QPushButton("Save")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._save)
        ctrl.addWidget(btn_save)
        
        layout.addLayout(ctrl)

    def _update_autocomplete_max(self, new_val):
        self.spin_autocomplete.setMaximum(new_val)
        if self.spin_autocomplete.value() > new_val:
            self.spin_autocomplete.setValue(new_val)

    def _test_telegram(self):
        from .telegram_bot import send_telegram_message
        import threading
        token = self.entry_token.text().strip()
        chat_id = self.entry_chat_id.text().strip()
        if token and chat_id:
            t = threading.Thread(
                target=send_telegram_message, 
                args=("👋 Hello from Decipline! Your Telegram integration is working perfectly.", token, chat_id),
                daemon=True
            )
            t.start()
            
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Test Sent", "Test message dispatched! Check your Telegram app.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Missing Info", "Please enter both Bot Token and Chat ID to test.")

    def _save(self):
        self.settings["focus_time"] = self.spin_focus.value()
        self.settings["short_break"] = self.spin_short.value()
        self.settings["long_break"] = self.spin_long.value()
        self.settings["autocomplete_minutes"] = self.spin_autocomplete.value()
        self.settings["sound_enabled"] = self.chk_sound.isChecked()
        self.settings["telegram_enabled"] = self.chk_tg.isChecked()
        self.settings["telegram_token"] = self.entry_token.text().strip()
        self.settings["telegram_chat_id"] = self.entry_chat_id.text().strip()
        save_settings(self.settings)
        self.accept()
