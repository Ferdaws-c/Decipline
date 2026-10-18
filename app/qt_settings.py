"""
qt_settings.py - PyQt6 Settings Dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSpinBox, QCheckBox, QLineEdit, QComboBox, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .qt_style import *
from .settings import load_settings, save_settings
from .qt_components import label, card

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(760, 560)
        self.resize(800, 590)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.settings = load_settings()
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 24)
        root.setSpacing(18)
        root.addWidget(label("Settings", "PageTitle"))
        root.addWidget(label("Choose how much you want to see."))
        mode_row = QHBoxLayout()
        mode_row.addWidget(label("App mode", "SectionTitle"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Basic · Simple controls", "basic")
        self.mode_combo.addItem("Expert · All features", "expert")
        self.mode_combo.setCurrentIndex(1 if self.settings.get("experience_mode") == "expert" else 0)
        mode_row.addWidget(self.mode_combo, 1)
        root.addLayout(mode_row)
        body = QHBoxLayout()
        body.setSpacing(16)
        focus_card, focus = card()
        focus.addWidget(label("Timer", "SectionTitle"))
        self._advanced_rows = []
        for title, name, maximum, key, default in (
            ("Study time", "spin_focus", 120, "focus_time", 25),
            ("Break time", "spin_short", 60, "short_break", 5),
            ("Long break", "spin_long", 120, "long_break", 30),
        ):
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(label(title, "MetricLabel"), 1)
            spin = QSpinBox()
            spin.setRange(1, maximum)
            spin.setValue(min(self.settings.get(key, default), maximum))
            spin.setSuffix(" min")
            spin.setFixedWidth(108)
            setattr(self, name, spin)
            row.addWidget(spin)
            focus.addWidget(holder)
            if key == "long_break":
                self._advanced_rows.append(holder)
        schedule_hint = label("Schedule tasks complete when a focus countdown finishes.")
        schedule_hint.setWordWrap(True)
        focus.addWidget(schedule_hint)
        self._advanced_rows.append(schedule_hint)
        self.chk_sound = QCheckBox("Play a sound when breaks end")
        self.chk_sound.setChecked(self.settings.get("sound_enabled", True))
        focus.addWidget(self.chk_sound)
        focus.addStretch()
        body.addWidget(focus_card, 1)

        telegram_card, telegram = card()
        self.telegram_card = telegram_card
        telegram.addWidget(label("Telegram notifications", "SectionTitle"))
        self.chk_tg = QCheckBox("Send notifications to my phone")
        self.chk_tg.setChecked(self.settings.get("telegram_enabled", False))
        telegram.addWidget(self.chk_tg)
        telegram.addWidget(label("BOT TOKEN", "MetricLabel"))
        self.entry_token = QLineEdit(self.settings.get("telegram_token", ""))
        self.entry_token.setPlaceholderText("Token from @BotFather")
        self.entry_token.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        telegram.addWidget(self.entry_token)
        telegram.addWidget(label("CHAT ID", "MetricLabel"))
        self.entry_chat_id = QLineEdit(self.settings.get("telegram_chat_id", ""))
        self.entry_chat_id.setPlaceholderText("Your Telegram chat ID")
        telegram.addWidget(self.entry_chat_id)
        test = QPushButton("Test connection")
        test.clicked.connect(self._test_telegram)
        telegram.addWidget(test)
        telegram.addStretch()
        body.addWidget(telegram_card, 1)
        root.addLayout(body, 1)
        controls = QHBoxLayout()
        controls.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        controls.addWidget(cancel)
        save = QPushButton("Save settings")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        controls.addWidget(save)
        root.addLayout(controls)
        self.mode_combo.currentIndexChanged.connect(self._update_mode_visibility)
        self._update_mode_visibility()

    def _update_mode_visibility(self):
        expert = self.mode_combo.currentData() == "expert"
        self.telegram_card.setVisible(expert)
        for row in self._advanced_rows:
            row.setVisible(expert)
        self.setMinimumSize(760 if expert else 480, 560)
        self.resize(800 if expert else 520, 650 if expert else 600)

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
        self.settings["experience_mode"] = self.mode_combo.currentData()
        self.settings["onboarding_completed"] = True
        self.settings["focus_time"] = self.spin_focus.value()
        self.settings["short_break"] = self.spin_short.value()
        self.settings["long_break"] = self.spin_long.value()
        self.settings["sound_enabled"] = self.chk_sound.isChecked()
        self.settings["telegram_enabled"] = self.chk_tg.isChecked()
        self.settings["telegram_token"] = self.entry_token.text().strip()
        self.settings["telegram_chat_id"] = self.entry_chat_id.text().strip()
        if not save_settings(self.settings):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Could not save", "Settings could not be saved. Please try again.")
            return
        self.accept()
