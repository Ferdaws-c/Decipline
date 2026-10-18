"""
qt_window.py - PyQt6 Main Window for Decipline.
Replaces the Tkinter/CustomTkinter implementation.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTableView,
    QHeaderView, QAbstractItemView, QFrame, QTabWidget, QProgressBar, QStackedWidget, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from .qt_style import *
from .pomodoro import PomodoroState, PomodoroTimer
from .storage import (
    load_schedule, get_display_rows, mark_task_completed, get_current_task_index,
    capture_schedule_target, complete_schedule_target
)
from .qt_library import LibraryDialog
from .qt_task_detail import TaskDetailDialog
from .notifier import show_notification
from .qt_schedule_model import ScheduleTableModel
from .qt_components import label, card, metric, prepare_table, scroll_page
from .settings import get_experience_mode, load_settings, save_settings
from .stats import get_courses

class PomodoroSignals(QObject):
    """Safely routes background thread callbacks to the main Qt GUI thread."""
    tick = pyqtSignal(int, object)          # remaining, state
    work_done = pyqtSignal()
    break_done = pyqtSignal()
    cycle_update = pyqtSignal(int)
    free_done = pyqtSignal()
    focus_completed = pyqtSignal(str, object)
    stats_saved = pyqtSignal(object)

class CustomTitleBar(QFrame):
    def __init__(self, parent=None, title="Decipline"):
        super().__init__(parent)
        self.window = parent
        self.setObjectName("HeaderPanel")
        self.setFixedHeight(70)
        
        layout = QHBoxLayout(self)
        self.header_layout = layout
        layout.setContentsMargins(26, 0, 26, 0)
        layout.setSpacing(12)

        mark = QLabel("d.")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        mark.setStyleSheet(f"background: {ACCENT}; color: #191326; border-radius: 10px; font-size: 24px; font-weight: 700;")
        layout.addWidget(mark)

        lbl_title = QLabel("decipline")
        self.brand_label = lbl_title
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; letter-spacing: -0.4px;")
        layout.addWidget(lbl_title)
        
        lbl_sub = label("Your space to make progress.")
        self.subtitle_label = lbl_sub
        layout.addWidget(lbl_sub)
        
        layout.addStretch()
        
        from .stats import check_streak
        streak = check_streak()
        lbl_streak = label(f"{streak} day streak", "Badge")
        self.streak_label = lbl_streak
        self.streak = streak
        lbl_streak.setFixedHeight(30)
        layout.addWidget(lbl_streak)

        self.mode_button = QPushButton("Expert mode")
        self.mode_button.clicked.connect(self.window.toggle_experience_mode)
        layout.addWidget(self.mode_button)
        
        btn_settings = QPushButton("Settings")
        btn_settings.setObjectName("QuietButton")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)
        
        btn_hide = QPushButton("Hide to Tray")
        self.hide_button = btn_hide
        btn_hide.setObjectName("QuietButton")
        btn_hide.setAccessibleName("Hide to tray")
        btn_hide.clicked.connect(self.window.hide_to_tray)
        layout.addWidget(btn_hide)
        close_button = QPushButton("Close")
        self.close_button = close_button
        close_button.setObjectName("QuietButton")
        close_button.setAccessibleName("Close app")
        close_button.setToolTip("Save your progress and exit Decipline completely")
        close_button.clicked.connect(self.window.close_app)
        layout.addWidget(close_button)
        
        self._is_tracking = False
        self._start_pos = None

    def _open_settings(self):
        from .qt_settings import SettingsDialog
        dlg = SettingsDialog(self.window)
        if dlg.exec():
            # If settings changed, we might want to update the timer if it's IDLE
            if self.window.timer.state == PomodoroState.IDLE:
                self.window.timer.reset()
            self.window.apply_experience_mode()
        dlg.deleteLater()

    def set_basic(self, basic):
        self.subtitle_label.hide()
        self.brand_label.setVisible(not basic)
        self.streak_label.setVisible(not basic)
        self.setFixedHeight(52 if basic else 70)
        self.header_layout.setContentsMargins(14 if basic else 26, 0, 14 if basic else 26, 0)
        self.header_layout.setSpacing(6 if basic else 12)
        self.hide_button.setText("Hide" if basic else "Hide to tray")
        self.hide_button.setToolTip("Hide the window and keep the timer running. Click the tray icon to reopen.")
        self.close_button.setText("×" if basic else "Close app")
        destination = "Expert" if basic else "Basic"
        self.mode_button.setText(f"{destination} mode")
        self.mode_button.setAccessibleName(f"Switch to {destination} mode")
        self.mode_button.setToolTip(f"Switch to {destination} mode. Your current timer keeps running.")
        self.mode_button.setStyleSheet("padding: 6px 8px; font-size: 11px;" if basic else "")
        for button in (self.hide_button, self.close_button):
            button.setStyleSheet("padding: 6px; min-width: 22px;" if basic else "")

    # Native-feeling window drag without lagging the event queue
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window.windowHandle()
            if handle and handle.startSystemMove():
                event.accept()
                return
            self._is_tracking = True
            self._start_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_tracking:
            self.window.move(event.globalPosition().toPoint() - self._start_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_tracking = False
            event.accept()


class MainWindow(QMainWindow):
    def __init__(self, on_hide=None):
        super().__init__()
        self._on_hide = on_hide
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setWindowTitle("Decipline")
        self.resize(1160, 820)
        self.setMinimumSize(980, 720)
        self.central = QFrame()
        self.central.setObjectName("MainPanel")
        self.central.setStyleSheet(f"QFrame#MainPanel {{ background: {BG}; border: 1px solid {BORDER}; }}")
        self.setCentralWidget(self.central)
        main_layout = QVBoxLayout(self.central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)
        self.mode_tabs = QTabWidget()
        self.mode_tabs.tabBar().hide()
        self.workspace = QStackedWidget()
        self.workspace.addWidget(self.mode_tabs)
        main_layout.addWidget(self.workspace)
        page = QWidget()
        page.setObjectName("Page")
        self.mode_tabs.addTab(scroll_page(page, minimum_height=590), "Scheduled routine")
        root = QVBoxLayout(page)
        root.setContentsMargins(22, 16, 22, 18)
        root.setSpacing(12)
        heading = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.lbl_schedule_title = label("Daily Routine", "PageTitle")
        self.lbl_schedule_title.setWordWrap(True)
        self.lbl_schedule_title.setMaximumHeight(54)
        self.lbl_schedule_title.setStyleSheet("font-size: 22px; font-weight: 600;")
        titles.addWidget(self.lbl_schedule_title)
        heading.addLayout(titles)
        heading.addStretch()
        for text, callback in (("Trends", self._open_trends), ("Schedule library", self._open_library)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            heading.addWidget(button)
        root.addLayout(heading)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        for title, attr, color in (("PLANNED TASKS", "task_count_value", None),
                                   ("COMPLETED", "completed_value", GREEN),
                                   ("PROGRESS", "progress_value", ACCENT)):
            frame, value = metric(title, "0", color)
            setattr(self, attr, value)
            metrics.addWidget(frame)

        body = QHBoxLayout()
        body.setSpacing(18)
        schedule_card, schedule_layout = card()
        section = QHBoxLayout()
        section.addWidget(label("Today's plan", "SectionTitle"))
        section.addStretch()
        from PyQt6.QtWidgets import QComboBox
        self.day_selector = QComboBox()
        self.day_selector.setMinimumWidth(120)
        self.day_selector.hide()
        self.day_selector.currentTextChanged.connect(self._on_day_changed)
        section.addWidget(self.day_selector)
        schedule_layout.addLayout(section)
        self.schedule_progress = QProgressBar()
        self.schedule_progress.setTextVisible(False)
        self.schedule_progress.setRange(0, 100)
        schedule_layout.addWidget(self.schedule_progress)
        self.table = QTableView()
        self.table_model = ScheduleTableModel(self.table)
        self.table.setModel(self.table_model)
        prepare_table(self.table)
        for column in (0, 2):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        for column in (1, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 86)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.doubleClicked.connect(lambda index: self._edit_task(index.row(), index.column()))
        schedule_layout.addWidget(self.table, 1)
        self.schedule_empty = QWidget()
        empty_layout = QVBoxLayout(self.schedule_empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(12)
        empty_layout.addWidget(label("Make space for a good day.", "SectionTitle"), alignment=Qt.AlignmentFlag.AlignCenter)
        message = label("Create a routine or import a schedule to get started.")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(message)
        open_library = QPushButton("Open schedule library")
        open_library.setObjectName("PrimaryButton")
        open_library.clicked.connect(self._open_library)
        empty_layout.addWidget(open_library, alignment=Qt.AlignmentFlag.AlignCenter)
        schedule_layout.addWidget(self.schedule_empty, 1)
        footer = QHBoxLayout()
        for text, color in (("● Completed", GREEN), ("● Current task", ACCENT)):
            legend = label(text, "MetricLabel")
            legend.setStyleSheet(f"color: {color};")
            footer.addWidget(legend)
        footer.addStretch()
        self.btn_reset_colors = QPushButton("Reset completion")
        self.btn_reset_colors.setObjectName("QuietButton")
        self.btn_reset_colors.clicked.connect(self._reset_colors)
        footer.addWidget(self.btn_reset_colors)
        schedule_layout.addLayout(footer)
        actions = QHBoxLayout()
        self.btn_mark_complete = QPushButton("Mark complete")
        self.btn_mark_complete.setObjectName("SuccessButton")
        self.btn_mark_complete.clicked.connect(self._mark_active_task_complete)
        self.btn_next_task = QPushButton("Next task")
        self.btn_next_task.clicked.connect(self._advance_task)
        actions.addWidget(self.btn_mark_complete, 1)
        actions.addWidget(self.btn_next_task)
        schedule_layout.addLayout(actions)
        schedule_column = QVBoxLayout()
        schedule_column.setSpacing(12)
        schedule_column.addLayout(metrics)
        schedule_column.addWidget(schedule_card, 1)
        body.addLayout(schedule_column, 1)

        timer_card, timer_layout = card()
        timer_layout.setContentsMargins(20, 16, 20, 16)
        timer_layout.setSpacing(6)
        timer_card.setFixedWidth(314)
        self.expert_timer_layout = timer_layout
        body.addWidget(timer_card)
        root.addLayout(body, 1)

        self.timer = PomodoroTimer()
        self.signals = PomodoroSignals()
        self.timer.on_tick = self.signals.tick.emit
        self.timer.on_work_done = self.signals.work_done.emit
        self.timer.on_break_done = self.signals.break_done.emit
        self.timer.on_cycle_update = self.signals.cycle_update.emit
        self.timer.on_free_timer_done = self.signals.free_done.emit
        self.timer.on_focus_completed = self.signals.focus_completed.emit
        self.timer.on_stats_update = lambda: self.signals.stats_saved.emit(get_courses())
        self.signals.work_done.connect(self._on_work_done)
        self.signals.break_done.connect(self._on_break_done)
        self.signals.free_done.connect(self._on_free_done)
        self.signals.focus_completed.connect(self._on_focus_completed)
        self._load_active_schedule()
        self.timer.reset()
        self.experience_mode = None
        self.expert_course_path = bool(load_settings().get("expert_course_path", True))
        from .qt_basic import BasicPanel
        self.basic_panel = BasicPanel(self)
        self.btn_start = self.basic_panel.start_btn
        self.btn_reset = self.basic_panel.stop_btn
        self.basic_surface, self.basic_surface_layout = card()
        self.basic_surface_layout.setContentsMargins(18, 16, 18, 16)
        basic_host = QWidget()
        host = QVBoxLayout(basic_host)
        host.setContentsMargins(12, 12, 12, 12)
        host.addWidget(self.basic_surface)
        host.addStretch()
        self.basic_page = scroll_page(basic_host, minimum_height=460)
        self.workspace.addWidget(self.basic_page)
        self.apply_experience_mode()

    @property
    def uses_course_path(self):
        if self.timer.session_id:
            return self.timer.focus_context is None
        return self.experience_mode != "expert" or self.expert_course_path

    def toggle_experience_mode(self):
        saved = load_settings()
        saved["experience_mode"] = "expert" if self.experience_mode == "basic" else "basic"
        saved["onboarding_completed"] = True
        if not save_settings(saved):
            QMessageBox.warning(self, "Could not switch mode", "Your choice could not be saved. Please try again.")
            return
        self.apply_experience_mode()

    def set_expert_course_path(self, checked):
        if self.experience_mode != "expert":
            return
        saved = load_settings()
        saved["expert_course_path"] = bool(checked)
        if not save_settings(saved):
            QMessageBox.warning(self, "Could not switch path", "Your choice could not be saved. Please try again.")
            self.basic_panel.sync()
            return
        old_path = self.uses_course_path
        self.expert_course_path = bool(checked)
        if old_path != bool(checked):
            self.timer.reset()
            self.timer.set_context(self.basic_panel.course.currentData() if checked else None,
                                   self.basic_panel.lecture.currentData() if checked else None)
        self.basic_panel.sync()

    def start_focus(self, seconds):
        if self.timer.state == PomodoroState.PAUSED:
            self.timer.start(track_tasks=False)
            return True
        target = None
        try:
            if self.uses_course_path:
                self.timer.set_context(self.basic_panel.course.currentData(), self.basic_panel.lecture.currentData())
            else:
                target = capture_schedule_target(getattr(self, "current_day", None))
                if target is None:
                    self._refresh_table()
                    return False
                self.timer.set_context(None, None)
                self._refresh_table()
            self.timer.start(seconds, track_tasks=False, focus_context=target)
        except OSError:
            QMessageBox.warning(self, "Could not start session", "The schedule could not be saved. Please try again.")
            return False
        return True

    def apply_experience_mode(self):
        mode = get_experience_mode()
        previous = self.experience_mode
        self.expert_course_path = bool(load_settings().get("expert_course_path", True))
        self.experience_mode = mode
        basic = mode == "basic"
        self.title_bar.set_basic(basic)
        if basic:
            self.basic_surface_layout.addWidget(self.basic_panel)
            self.workspace.setCurrentWidget(self.basic_page)
            self.setMinimumSize(400, 520)
            if previous != mode:
                self.resize(440, 570)
        else:
            self.expert_timer_layout.addWidget(self.basic_panel)
            self.workspace.setCurrentWidget(self.mode_tabs)
            self.setMinimumSize(980, 720)
            if previous != mode:
                self.resize(1160, 820)
        self.basic_panel.history_btn.setVisible(basic)
        self.basic_panel.sync()

    def hide_to_tray(self):
        self.hide()
        if self._on_hide:
            self._on_hide()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def close_app(self):
        self.timer.shutdown()
        QApplication.instance().quit()

    def closeEvent(self, event):
        event.accept()
        self.close_app()

    def _open_library(self):
        from .qt_library import LibraryDialog
        dlg = LibraryDialog(self)
        dlg.exec()
        dlg.deleteLater()
        self._load_active_schedule()

    def _advance_task(self):
        from .storage import advance_task_index
        advance_task_index(getattr(self, 'current_day', None))
        self._refresh_table()

    def _mark_active_task_complete(self):
        day = getattr(self, 'current_day', None)
        active_idx = get_current_task_index(day)
        
        # Determine which task to mark: selected in table, or the active one
        selected_rows = self.table.selectionModel().selectedRows()
        target_idx = selected_rows[0].row() if selected_rows else active_idx
        
        schedule = load_schedule(day)
        tasks = schedule.get("tasks", []) if schedule else []
        if 0 <= target_idx < len(tasks):
            newly_completed = not tasks[target_idx].get("completed")
            mark_task_completed(target_idx, day)
            if newly_completed:
                from .stats import add_task_completed
                add_task_completed()
            # Only advance if the task marked was the currently ongoing one
            if target_idx == active_idx:
                self._advance_task()
            else:
                self._refresh_table()

    def _reset_colors(self):
        from .storage import load_schedule, save_active_schedule
        from PyQt6.QtWidgets import QMessageBox
        
        day = getattr(self, 'current_day', None)
        sched = load_schedule(day)
        if sched:
            msg = QMessageBox(self)
            msg.setWindowTitle("Reset Colors")
            msg.setText("Are you sure you want to reset all tasks to uncompleted for this schedule?\n(This does not reset your study stats or hours)")
            msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if msg.exec() == QMessageBox.StandardButton.Yes:
                tasks = sched.get("tasks", [])
                for t in tasks:
                    t["completed"] = False
                save_active_schedule(tasks, day)
                self._refresh_table()

    def _open_trends(self):
        from .qt_trends import TrendsDialog
        dlg = TrendsDialog(self)
        self.signals.stats_saved.connect(dlg.refresh)
        dlg.exec()
        dlg.deleteLater()

    def _on_day_changed(self, text):
        if text:
            self.current_day = text
            self._refresh_table()

    def _load_active_schedule(self):
        self.current_day = None
        sched = load_schedule()
        if sched:
            if sched.get("is_weekly"):
                # It's a weekly schedule, update UI
                self.lbl_schedule_title.setText(sched.get("name").split(" (")[0])
                
                self.day_selector.blockSignals(True)
                self.day_selector.clear()
                days = list(sched.get("weekly_data", {}).keys())
                if sched.get("day") not in days:
                    days.append(sched.get("day"))
                self.day_selector.addItems(days)
                self.day_selector.setCurrentText(sched.get("day"))
                self.day_selector.blockSignals(False)
                self.day_selector.show()
                self.current_day = sched.get("day")
            else:
                self.lbl_schedule_title.setText(sched.get("name", "Schedule"))
                self.day_selector.hide()
                
        self._refresh_table(sched)

    def _refresh_table(self, sched=None):
        if sched is None:
            sched = load_schedule(getattr(self, 'current_day', None))
        if not sched:
            self.table_model.set_rows([])
            self._update_schedule_summary([])
            return
            
        rows = get_display_rows(sched)
        active_index = sched.get("active_task_index", 0)
        self.table_model.set_rows(rows, active_index)
        self._update_schedule_summary(rows)

    def _update_schedule_summary(self, rows):
        index = self.table_model._active_index or 0
        pending = [row for row in rows[max(0, index):] if not row[4]]
        self.schedule_focus_name = pending[0][1] if pending else "No unfinished task · open the schedule library"
        self.schedule_focus_available = bool(pending)
        completed = sum(bool(row[4]) for row in rows)
        progress = round(completed * 100 / len(rows)) if rows else 0
        self.task_count_value.setText(str(len(rows)))
        self.completed_value.setText(str(completed))
        self.progress_value.setText(f"{progress}%")
        self.schedule_progress.setValue(progress)
        self.table.setVisible(bool(rows))
        self.schedule_empty.setVisible(not rows)
        for button in (self.btn_mark_complete, self.btn_next_task, self.btn_reset_colors):
            button.setEnabled(bool(rows))
        if hasattr(self, "basic_panel"):
            self.basic_panel.sync()

    def _edit_task(self, row, col):
        sched = load_schedule(self.current_day) if hasattr(self, 'current_day') and self.current_day else load_schedule()
        if not sched or row >= len(sched.get("tasks", [])): return
        
        task = sched["tasks"][row]
        dlg = TaskDetailDialog(self, task, row, getattr(self, 'current_day', None))
        if dlg.exec():
            self._load_active_schedule()
        dlg.deleteLater()

    def _toggle_timer(self):
        self.basic_panel._toggle()

    def _reset_timer(self):
        self.basic_panel._stop()

    def _on_focus_completed(self, session_id, target):
        if target is None:
            return
        try:
            if complete_schedule_target(target):
                from .stats import add_task_completed
                add_task_completed()
        except OSError:
            QMessageBox.warning(self, "Could not complete task", "Your study time is kept. Try marking the task complete again.")
        self._refresh_table()

    def _on_work_done(self):
        self.basic_panel.sync()
        self._notify_phase("Focus complete", "Your study time is saved. Start a break when ready.")

    def _on_break_done(self):
        self.basic_panel.sync()
        self._notify_phase("Break complete", "Ready for your next focus session.")

    def _on_free_done(self):
        self.basic_panel.sync()
        self._notify_phase("Timer complete", "Your timer has finished.")

    def _notify_phase(self, title, message):
        if load_settings().get("sound_enabled", True):
            import winsound
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        show_notification(title, message)
        from .telegram_bot import notify_async
        notify_async(f"{title}: {message}")
