"""
qt_task_editor.py - Full CRUD task editor for a schedule (daily or weekly).
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox,
    QLineEdit, QSpinBox, QTextEdit, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from .qt_style import *
from .storage import (
    get_schedule_by_id, get_schedule_tasks, save_schedule_tasks
)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class SingleTaskDialog(QDialog):
    """Add or edit a single task."""
    def __init__(self, parent=None, task=None):
        super().__init__(parent)
        self.setWindowTitle("Add Task" if not task else "Edit Task")
        self.setFixedSize(380, 280)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        lbl = QLabel("Add Task" if not task else "Edit Task")
        lbl.setFont(QFont(FONT_UI, 14, QFont.Weight.Bold))
        layout.addWidget(lbl)
        
        self.task = task

        # Time
        row_time = QHBoxLayout()
        row_time.addWidget(QLabel("Time (HH:MM):"))
        self.entry_time = QLineEdit(task.get("time", "") if task else "")
        self.entry_time.setPlaceholderText("e.g. 09:00")
        row_time.addWidget(self.entry_time)
        layout.addLayout(row_time)

        # Task Name
        layout.addWidget(QLabel("Task Name:"))
        self.entry_name = QLineEdit(task.get("text", "") if task else "")
        self.entry_name.setPlaceholderText("e.g. Morning Workout")
        layout.addWidget(self.entry_name)

        # Duration
        row_dur = QHBoxLayout()
        row_dur.addWidget(QLabel("Duration (min):"))
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(0, 480)
        dur_val = 0
        if task:
            try:
                dur_str = str(task.get("duration", 0)).lower().replace("min", "").strip()
                dur_val = int(dur_str)
            except ValueError:
                dur_val = 0
        self.spin_dur.setValue(dur_val)
        row_dur.addWidget(self.spin_dur)
        layout.addLayout(row_dur)

        # Notes
        layout.addWidget(QLabel("Notes:"))
        self.entry_notes = QLineEdit(task.get("notes", "") if task else "")
        self.entry_notes.setPlaceholderText("Optional notes")
        layout.addWidget(self.entry_notes)

        layout.addStretch()

        # Buttons
        ctrl = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        ctrl.addWidget(btn_cancel)

        btn_save = QPushButton("Save Task")
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._save)
        ctrl.addWidget(btn_save)
        layout.addLayout(ctrl)

        self.result_task = None

    def _save(self):
        name = self.entry_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Field", "Task name cannot be empty.")
            return
        
        is_completed = self.task.get("completed", False) if hasattr(self, 'task') and self.task else False
        
        self.result_task = {
            "time": self.entry_time.text().strip(),
            "text": name,
            "duration": self.spin_dur.value(),
            "notes": self.entry_notes.text().strip(),
            "completed": is_completed
        }
        self.accept()


class TaskEditorDialog(QDialog):
    """Full CRUD task list editor for a specific schedule (and optional day)."""
    def __init__(self, parent=None, sid=None, schedule_name="", schedule_type="daily"):
        super().__init__(parent)
        self.sid = sid
        self.schedule_type = schedule_type
        self.current_day = DAYS[0]

        self.setWindowTitle(f"Edit Tasks — {schedule_name}")
        self.setMinimumSize(700, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel(f"✏️ {schedule_name}")
        lbl.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        hdr.addWidget(lbl)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Day selector (weekly only)
        if schedule_type == "weekly":
            day_row = QHBoxLayout()
            day_row.addWidget(QLabel("Select Day:"))
            self.day_combo = QComboBox()
            self.day_combo.addItems(DAYS)
            self.day_combo.setFixedWidth(140)
            self.day_combo.currentTextChanged.connect(self._on_day_changed)
            day_row.addWidget(self.day_combo)
            day_row.addStretch()
            layout.addLayout(day_row)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Task", "Duration", "Notes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color: {BG}; border: 1px solid {BORDER}; gridline-color: {BORDER}; }}
            QHeaderView::section {{ background-color: {PANEL_BG}; padding: 4px; border: 1px solid {BORDER}; }}
        """)
        layout.addWidget(self.table)

        # Controls
        ctrl = QHBoxLayout()

        btn_add = QPushButton("+ Add Task")
        btn_add.setObjectName("PrimaryButton")
        btn_add.clicked.connect(self._add_task)
        ctrl.addWidget(btn_add)

        btn_edit = QPushButton("✏️ Edit")
        btn_edit.clicked.connect(self._edit_task)
        ctrl.addWidget(btn_edit)

        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.setStyleSheet("background-color: #EF4444; color: white;")
        btn_delete.clicked.connect(self._delete_task)
        ctrl.addWidget(btn_delete)

        ctrl.addStretch()

        btn_up = QPushButton("▲")
        btn_up.setFixedWidth(36)
        btn_up.clicked.connect(self._move_up)
        ctrl.addWidget(btn_up)

        btn_down = QPushButton("▼")
        btn_down.setFixedWidth(36)
        btn_down.clicked.connect(self._move_down)
        ctrl.addWidget(btn_down)

        layout.addLayout(ctrl)

        self._refresh_table()

    def _on_day_changed(self, day):
        self.current_day = day
        self._refresh_table()

    def _get_tasks(self):
        day = self.current_day if self.schedule_type == "weekly" else None
        return list(get_schedule_tasks(self.sid, day))

    def _save_tasks(self, tasks):
        day = self.current_day if self.schedule_type == "weekly" else None
        save_schedule_tasks(self.sid, tasks, day)

    def _refresh_table(self):
        tasks = self._get_tasks()
        self.table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            is_done = task.get("completed", False)
            color = QColor(GREEN) if is_done else QColor(TXT_SEC)
            for j, val in enumerate([
                task.get("time", ""),
                task.get("text", ""),
                f"{str(task.get('duration', 0)).lower().replace('min', '').strip()} min",
                task.get("notes", "")
            ]):
                item = QTableWidgetItem(val)
                item.setForeground(color)
                self.table.setItem(i, j, item)

    def _selected_row(self):
        rows = self.table.selectedItems()
        if rows:
            return self.table.currentRow()
        return -1

    def _add_task(self):
        dlg = SingleTaskDialog(self)
        if dlg.exec() and dlg.result_task:
            tasks = self._get_tasks()
            tasks.append(dlg.result_task)
            self._save_tasks(tasks)
            self._refresh_table()

    def _edit_task(self):
        row = self._selected_row()
        if row < 0:
            QMessageBox.information(self, "Select a task", "Please select a task to edit.")
            return
        tasks = self._get_tasks()
        dlg = SingleTaskDialog(self, task=tasks[row])
        if dlg.exec() and dlg.result_task:
            tasks[row] = dlg.result_task
            self._save_tasks(tasks)
            self._refresh_table()

    def _delete_task(self):
        row = self._selected_row()
        if row < 0:
            return
        tasks = self._get_tasks()
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Task")
        msg.setText(f"Delete \"{tasks[row].get('text', 'this task')}\"?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            tasks.pop(row)
            self._save_tasks(tasks)
            self._refresh_table()

    def _move_up(self):
        row = self._selected_row()
        if row <= 0:
            return
        tasks = self._get_tasks()
        tasks[row], tasks[row - 1] = tasks[row - 1], tasks[row]
        self._save_tasks(tasks)
        self._refresh_table()
        self.table.selectRow(row - 1)

    def _move_down(self):
        row = self._selected_row()
        tasks = self._get_tasks()
        if row < 0 or row >= len(tasks) - 1:
            return
        tasks[row], tasks[row + 1] = tasks[row + 1], tasks[row]
        self._save_tasks(tasks)
        self._refresh_table()
        self.table.selectRow(row + 1)
