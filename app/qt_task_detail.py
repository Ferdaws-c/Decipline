"""
qt_task_detail.py - PyQt6 Task Detail Popup.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .qt_style import *
from .storage import postpone_task, complete_task

class TaskDetailDialog(QDialog):
    def __init__(self, parent, task, row_index, day_of_week=None):
        super().__init__(parent)
        self.task = task
        self.row_index = row_index
        self.day_of_week = day_of_week
        self.setWindowTitle("Task Details")
        self.setFixedSize(400, 350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("Task Details")
        lbl.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        layout.addWidget(lbl)
        
        layout.addWidget(QLabel("Task Name:"))
        self.entry_name = QLineEdit(self.task.get("text", ""))
        self.entry_name.setReadOnly(True)
        layout.addWidget(self.entry_name)
        
        layout.addWidget(QLabel("Notes:"))
        self.entry_notes = QTextEdit(self.task.get("notes", ""))
        self.entry_notes.setReadOnly(True)
        layout.addWidget(self.entry_notes)
        
        ctrl = QHBoxLayout()
        
        btn_delete = QPushButton("Delete")
        btn_delete.setStyleSheet("background-color: #EF4444; color: white;")
        btn_delete.clicked.connect(self._delete)
        ctrl.addWidget(btn_delete)
        
        btn_postpone = QPushButton("Postpone (-15m)")
        btn_postpone.clicked.connect(self._postpone)
        ctrl.addWidget(btn_postpone)
        
        btn_start_task = QPushButton("Start Task")
        btn_start_task.clicked.connect(self._start_task)
        btn_start_task.setStyleSheet("font-weight: bold;")
        ctrl.addWidget(btn_start_task)
        
        layout.addLayout(ctrl)

    def _postpone(self):
        from .storage import check_postpone_overlap
        if check_postpone_overlap(self.row_index, 15, self.day_of_week):
            from PyQt6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setWindowTitle("Schedule Conflict")
            msg.setText("Postponing this task will overlap with the next one.\nDo you want to Replace the overlapping tasks, or Push everything down?")
            btn_replace = msg.addButton("Replace", QMessageBox.ButtonRole.ActionRole)
            btn_push = msg.addButton("Push", QMessageBox.ButtonRole.ActionRole)
            msg.addButton(QMessageBox.StandardButton.Cancel)
            msg.exec()
            
            if msg.clickedButton() == btn_replace:
                postpone_task(self.row_index, 15, mode="replace", day_of_week=self.day_of_week)
            elif msg.clickedButton() == btn_push:
                postpone_task(self.row_index, 15, mode="push", day_of_week=self.day_of_week)
            else:
                return # Cancelled
        else:
            postpone_task(self.row_index, 15, mode="push", day_of_week=self.day_of_week)
            
        self.accept()

    def _start_task(self):
        from .storage import set_active_task_index
        set_active_task_index(self.row_index, self.day_of_week)
        if hasattr(self.parent(), '_refresh_table'):
            self.parent()._refresh_table()
        self.accept()

    def _delete(self):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Task")
        msg.setText("Are you sure you want to delete this task?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            complete_task(self.row_index, self.day_of_week)
            self.accept()
