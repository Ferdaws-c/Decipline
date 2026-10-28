"""
qt_settings.py - PyQt6 Settings Dialog.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QSpinBox, QCheckBox, QLineEdit, QComboBox, QWidget
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont

from .qt_style import *
from .settings import load_settings, save_settings
from .qt_components import label, card


class TelegramSettingsSignals(QObject):
    finished = pyqtSignal(str, object, object)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(760, 560)
        self.resize(800, 590)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.settings = load_settings()
        self._telegram_help_dialog = None
        self._telegram_busy = False
        self._telegram_signals = TelegramSettingsSignals(self)
        self._telegram_signals.finished.connect(self._telegram_finished)
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
        self.chk_sound = QCheckBox("Play a sound when timers finish")
        self.chk_sound.setChecked(self.settings.get("sound_enabled", True))
        focus.addWidget(self.chk_sound)
        focus.addStretch()
        body.addWidget(focus_card, 1)

        telegram_card, telegram = card()
        self.telegram_card = telegram_card
        telegram.addWidget(label("Telegram notifications", "SectionTitle"))
        self.telegram_help_btn = QPushButton("How to set up Telegram")
        self.telegram_help_btn.setObjectName("QuietButton")
        self.telegram_help_btn.clicked.connect(self._open_telegram_help)
        telegram.addWidget(self.telegram_help_btn)
        hint = label("Get a phone reminder when your break ends. Setup is optional.", "MetricLabel")
        hint.setWordWrap(True)
        telegram.addWidget(hint)
        self.chk_tg = QCheckBox("Notify me when a break ends")
        self.chk_tg.setChecked(self.settings.get("telegram_enabled", False))
        telegram.addWidget(self.chk_tg)
        telegram.addWidget(label("BOT TOKEN", "MetricLabel"))
        self.entry_token = QLineEdit(self.settings.get("telegram_token", ""))
        self.entry_token.setPlaceholderText("Token from @BotFather")
        self.entry_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry_token.setAccessibleName("Telegram bot token")
        telegram.addWidget(self.entry_token)
        telegram.addWidget(label("CHAT ID", "MetricLabel"))
        self.entry_chat_id = QLineEdit(self.settings.get("telegram_chat_id", ""))
        self.entry_chat_id.setPlaceholderText("Your Telegram chat ID")
        self.entry_chat_id.setAccessibleName("Telegram chat ID")
        telegram.addWidget(self.entry_chat_id)
        self.find_chat_btn = QPushButton("Find my chat ID")
        self.find_chat_btn.clicked.connect(self._find_chat_id)
        telegram.addWidget(self.find_chat_btn)
        self.test_telegram_btn = QPushButton("Test connection")
        self.test_telegram_btn.clicked.connect(self._test_telegram)
        telegram.addWidget(self.test_telegram_btn)
        self.telegram_status = label("", "MetricLabel")
        self.telegram_status.setWordWrap(True)
        telegram.addWidget(self.telegram_status)
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
        self.setMinimumSize(760 if expert else 480, 680 if expert else 560)
        self.resize(800 if expert else 520, 720 if expert else 600)

    def _open_telegram_help(self):
        from .qt_telegram_help import TelegramHelpDialog
        if self._telegram_help_dialog is None:
            dialog = TelegramHelpDialog(self)
            self._telegram_help_dialog = dialog
            def finished(*_):
                self._telegram_help_dialog = None
                dialog.deleteLater()
            dialog.finished.connect(finished)
            dialog.open()
        self._telegram_help_dialog.raise_()
        self._telegram_help_dialog.activateWindow()

    def _find_chat_id(self):
        self._run_telegram_action("find")

    def _test_telegram(self):
        self._run_telegram_action("test")

    def _run_telegram_action(self, action):
        import threading
        from .telegram_bot import find_private_chat_id, send_test_message, TelegramError
        if self._telegram_busy:
            return
        token = self.entry_token.text().strip()
        chat_id = self.entry_chat_id.text().strip()
        if not token or (action == "test" and not chat_id):
            self.telegram_status.setText("Paste your bot token first." if not token else "Click Find my chat ID, or enter your chat ID first.")
            return
        self._telegram_busy = True
        self.find_chat_btn.setEnabled(False)
        self.test_telegram_btn.setEnabled(False)
        self.telegram_status.setStyleSheet("")
        self.telegram_status.setText("Looking for your chat…" if action == "find" else "Sending a test message…")
        signals = self._telegram_signals
        def worker():
            try:
                value = find_private_chat_id(token) if action == "find" else send_test_message(token, chat_id)
                result = {"ok": True, "value": value}
            except TelegramError as error:
                result = {"ok": False, "message": str(error)}
            except Exception:
                result = {"ok": False, "message": "Could not connect to Telegram. Check your details and try again."}
            try:
                signals.finished.emit(action, (token, chat_id), result)
            except RuntimeError:
                pass  # The user may have closed Settings while the request finished.
        threading.Thread(target=worker, daemon=True, name="TelegramSetup").start()

    def _telegram_finished(self, action, context, result):
        self._telegram_busy = False
        self.find_chat_btn.setEnabled(True)
        self.test_telegram_btn.setEnabled(True)
        if (self.entry_token.text().strip() != context[0] or self.entry_chat_id.text().strip() != context[1]):
            self.telegram_status.setText("Your details changed. Try again with the new details.")
            return
        if not result["ok"]:
            self.telegram_status.setStyleSheet(f"color: {AMBER};")
            self.telegram_status.setText(result["message"])
            return
        self.telegram_status.setStyleSheet(f"color: {GREEN};")
        if action == "find":
            self.entry_chat_id.setText(result["value"])
            self.telegram_status.setText("Chat ID found. Click Test connection, then turn on reminders and save.")
        else:
            self.telegram_status.setText("Test message sent. Check Telegram, then turn on reminders and save.")

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
