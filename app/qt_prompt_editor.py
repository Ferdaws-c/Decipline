"""Persistent daily and weekly schedule prompts used by the library's Copy button."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
                            QPlainTextEdit, QPushButton, QMessageBox)

from .ai_prompt import (get_daily_prompt, get_weekly_prompt,
                        get_default_daily_prompt, get_default_weekly_prompt)
from .settings import load_settings, save_settings
from .qt_components import label


class PromptEditorDialog(QDialog):
    def __init__(self, parent=None, kind="daily"):
        super().__init__(parent)
        self.setWindowTitle("Schedule prompts")
        self.resize(840, 700)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)
        root.addWidget(label("MAKE THE PLAN YOURS", "Eyebrow"))
        root.addWidget(label("Schedule prompts", "PageTitle"))
        hint = QLabel("Edit the text that Copy Prompt sends to your clipboard. Keep the JSON format "
                      "instructions so the generated schedule can still be imported.")
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        root.addWidget(hint)
        self.tabs = QTabWidget()
        self.daily = QPlainTextEdit(get_daily_prompt())
        self.weekly = QPlainTextEdit(get_weekly_prompt())
        self.tabs.addTab(self.daily, "Daily prompt")
        self.tabs.addTab(self.weekly, "Weekly prompt")
        self.tabs.setCurrentIndex(1 if kind == "weekly" else 0)
        root.addWidget(self.tabs)
        controls = QHBoxLayout()
        reset = QPushButton("Restore default for this tab")
        reset.setObjectName("QuietButton")
        reset.clicked.connect(self.restore_default)
        controls.addWidget(reset)
        controls.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        controls.addWidget(cancel)
        save = QPushButton("Save prompts")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self.save)
        controls.addWidget(save)
        root.addLayout(controls)

    def restore_default(self):
        if self.tabs.currentIndex() == 0:
            self.daily.setPlainText(get_default_daily_prompt())
        else:
            self.weekly.setPlainText(get_default_weekly_prompt())

    def save(self):
        daily, weekly = self.daily.toPlainText(), self.weekly.toPlainText()
        if not daily.strip() or not weekly.strip():
            QMessageBox.warning(self, "Empty prompt", "Both prompts need text. Use Restore default if needed.")
            return
        settings = load_settings()
        settings.update(daily_prompt=daily, weekly_prompt=weekly)
        if not save_settings(settings):
            QMessageBox.warning(self, "Could not save", "Your prompts could not be saved. Please try again.")
            return
        self.accept()
