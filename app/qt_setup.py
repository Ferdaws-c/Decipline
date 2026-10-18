"""A one-time, optional-complexity choice before opening the workspace."""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from .qt_components import label, card
from .settings import load_settings, save_settings


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Decipline")
        self.setMinimumSize(620, 440)
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 28, 30, 28)
        root.setSpacing(18)
        root.addWidget(label("Welcome to Decipline", "PageTitle"))
        root.addWidget(label("How would you like to use the app?"))
        self.mode = "basic"
        self.basic_btn = QPushButton("Basic · Recommended")
        self.expert_btn = QPushButton("Expert")
        for button, mode, description in (
            (self.basic_btn, "basic", "A simple timer, course study, and your history."),
            (self.expert_btn, "expert", "Full dashboards, schedules, AI prompts, and advanced settings."),
        ):
            panel, content = card()
            button.setCheckable(True)
            button.clicked.connect(lambda checked, value=mode: self.choose(value))
            content.addWidget(button)
            hint = label(description)
            hint.setWordWrap(True)
            content.addWidget(hint)
            root.addWidget(panel)
        root.addWidget(label("You can change this any time in Settings."))
        actions = QHBoxLayout()
        actions.addStretch()
        continue_btn = QPushButton("Get started")
        continue_btn.setObjectName("PrimaryButton")
        continue_btn.clicked.connect(self.save_choice)
        actions.addWidget(continue_btn)
        root.addLayout(actions)
        self.choose("basic")

    def choose(self, mode):
        self.mode = mode
        self.basic_btn.setChecked(mode == "basic")
        self.expert_btn.setChecked(mode == "expert")

    def save_choice(self):
        settings = load_settings()
        settings.update(experience_mode=self.mode, onboarding_completed=True)
        if not save_settings(settings):
            QMessageBox.warning(self, "Could not save", "Your choice could not be saved. Please try again.")
            return
        self.accept()
