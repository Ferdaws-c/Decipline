"""
qt_library.py - PyQt6 Schedule Library Popup.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QListWidget, QListWidgetItem, QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from .qt_style import *
from .storage import (
    get_daily_schedules, get_weekly_schedules, 
    set_active_schedule, create_daily_schedule, create_weekly_schedule,
    delete_schedule, rename_schedule, get_schedule_by_id,
    create_empty_daily_schedule, create_empty_weekly_schedule
)

class LibraryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule Library")
        self.setMinimumSize(700, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        self.active_tab = "daily"
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        
        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("📚 Schedule Library")
        lbl.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        hdr.addWidget(lbl)
        hdr.addStretch()
        
        self.btn_daily = QPushButton("Daily")
        self.btn_daily.clicked.connect(lambda: self._switch_tab("daily"))
        self.btn_weekly = QPushButton("Weekly")
        self.btn_weekly.clicked.connect(lambda: self._switch_tab("weekly"))
        hdr.addWidget(self.btn_daily)
        hdr.addWidget(self.btn_weekly)
        layout.addLayout(hdr)
        
        # Action bar
        action_bar = QHBoxLayout()

        self.btn_prompt = QPushButton("🤖 Copy Prompt")
        self.btn_prompt.clicked.connect(self._copy_prompt)
        action_bar.addWidget(self.btn_prompt)

        action_bar.addStretch()

        btn_create = QPushButton("+ Create New")
        btn_create.clicked.connect(self._create_new)
        action_bar.addWidget(btn_create)

        btn_import = QPushButton("📥 Import AI JSON")
        btn_import.setObjectName("PrimaryButton")
        btn_import.clicked.connect(self._import_new)
        action_bar.addWidget(btn_import)

        layout.addLayout(action_bar)
        
        # List
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # Controls
        ctrl = QHBoxLayout()

        btn_edit_tasks = QPushButton("✏️ Edit Tasks")
        btn_edit_tasks.setObjectName("PrimaryButton")
        btn_edit_tasks.clicked.connect(self._edit_tasks)
        ctrl.addWidget(btn_edit_tasks)

        btn_rename = QPushButton("Rename")
        btn_rename.clicked.connect(self._rename_selected)
        ctrl.addWidget(btn_rename)

        btn_delete = QPushButton("Delete")
        btn_delete.setStyleSheet("background-color: #EF4444; color: white;")
        btn_delete.clicked.connect(self._delete_selected)
        ctrl.addWidget(btn_delete)
        
        ctrl.addStretch()
        
        btn_activate = QPushButton("✅ Set Active")
        btn_activate.setObjectName("PrimaryButton")
        btn_activate.clicked.connect(self._activate_selected)
        ctrl.addWidget(btn_activate)
        
        layout.addLayout(ctrl)
        
        self._refresh()

    def _switch_tab(self, tab):
        self.active_tab = tab
        if tab == "daily":
            self.btn_daily.setStyleSheet(f"background-color: {BORDER};")
            self.btn_weekly.setStyleSheet("")
            self.btn_prompt.setText("🤖 Copy Daily Prompt")
        else:
            self.btn_weekly.setStyleSheet(f"background-color: {BORDER};")
            self.btn_daily.setStyleSheet("")
            self.btn_prompt.setText("🤖 Copy Weekly Prompt")
        self._refresh()

    def _copy_prompt(self):
        from PyQt6.QtWidgets import QApplication
        from .ai_prompt import get_daily_prompt, get_weekly_prompt
        from .notifier import show_notification
        
        prompt = get_daily_prompt() if self.active_tab == "daily" else get_weekly_prompt()
        QApplication.clipboard().setText(prompt)
        show_notification("Copied!", f"{self.active_tab.capitalize()} AI prompt copied to clipboard.")

    def _refresh(self):
        self.list_widget.clear()
        if self.active_tab == "daily":
            items = get_daily_schedules()
        else:
            items = get_weekly_schedules()
            
        for i, sched in enumerate(items):
            item = QListWidgetItem(sched.get("name", "Unnamed"))
            item.setData(Qt.ItemDataRole.UserRole, sched.get("id"))
            self.list_widget.addItem(item)

    def _get_selected_id(self):
        selected = self.list_widget.selectedItems()
        if selected:
            return selected[0].data(Qt.ItemDataRole.UserRole)
        return None

    def _on_item_double_clicked(self, item):
        self._edit_tasks()

    def _activate_selected(self):
        sid = self._get_selected_id()
        if sid:
            set_active_schedule(sid)
            self.accept()

    def _edit_tasks(self):
        sid = self._get_selected_id()
        if not sid:
            QMessageBox.information(self, "Select a schedule", "Please select a schedule from the list first.")
            return
        sched = get_schedule_by_id(sid)
        if not sched:
            return
        from .qt_task_editor import TaskEditorDialog
        dlg = TaskEditorDialog(self, sid=sid, schedule_name=sched["name"], schedule_type=sched["type"])
        dlg.exec()
        # Refresh parent window too
        if self.parent():
            self.parent()._load_active_schedule()

    def _create_new(self):
        name, ok = QInputDialog.getText(self, "New Schedule", "Schedule name:")
        if not ok or not name.strip():
            return
        if self.active_tab == "daily":
            create_empty_daily_schedule(name.strip())
        else:
            create_empty_weekly_schedule(name.strip())
        self._refresh()

    def _rename_selected(self):
        sid = self._get_selected_id()
        if not sid: return
        name, ok = QInputDialog.getText(self, "Rename", "New schedule name:")
        if ok and name:
            rename_schedule(sid, name)
            self._refresh()

    def _delete_selected(self):
        sid = self._get_selected_id()
        if not sid: return
        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Schedule")
        msg.setText("Are you sure you want to permanently delete this schedule?")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            delete_schedule(sid)
            self._refresh()

    def _import_new(self):
        import json
        text, ok = QInputDialog.getMultiLineText(self, "Import AI Schedule", "Paste the JSON generated by the AI:")
        if not ok or not text.strip():
            return
            
        try:
            json_text = text
            if "```json" in text:
                json_text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                json_text = text.split("```")[1].split("```")[0].strip()
                
            data = json.loads(json_text)
            
            if isinstance(data, dict):
                name, ok = QInputDialog.getText(self, "Schedule Name", "Name this weekly schedule:")
                if not ok or not name:
                    name = "AI Weekly Schedule"
                create_weekly_schedule(name, data)
                self.active_tab = "weekly"
                
            elif isinstance(data, list):
                name, ok = QInputDialog.getText(self, "Schedule Name", "Name this daily schedule:")
                if not ok or not name:
                    name = "AI Daily Schedule"
                create_daily_schedule(name, data)
                self.active_tab = "daily"
            else:
                raise ValueError("JSON must be a list (daily) or a dict of days (weekly).")
                
            self._refresh()
        except Exception as e:
            from .notifier import show_notification
            show_notification("Import Failed", f"Invalid JSON format. {str(e)}")

