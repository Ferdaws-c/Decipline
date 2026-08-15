"""
qt_window.py - PyQt6 Main Window for Decipline.
Replaces the Tkinter/CustomTkinter implementation.
"""

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QObject, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath

from .qt_style import *
from .pomodoro import PomodoroState, PomodoroTimer
from .storage import (
    load_schedule, get_display_rows, mark_task_completed, get_current_task_index
)
from .qt_library import LibraryDialog
from .qt_task_detail import TaskDetailDialog
from .notifier import show_notification

class PomodoroSignals(QObject):
    """Safely routes background thread callbacks to the main Qt GUI thread."""
    tick = pyqtSignal(int, object)          # remaining, state
    work_done = pyqtSignal()
    break_done = pyqtSignal()
    cycle_update = pyqtSignal(int)
    free_done = pyqtSignal()
    task_completed = pyqtSignal()

class TimerWidget(QWidget):
    """Custom widget that draws the Pomodoro progress arc and text."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)
        self.fraction = 1.0
        self.text_time = "25:00"
        self.text_state = "Focus Time"
        self.color_state = GREEN
        self.cycle = 0
        
    def update_state(self, fraction, time_str, state_str, color, cycle=0):
        self.fraction = fraction
        self.text_time = time_str
        self.text_state = state_str
        self.color_state = color
        self.cycle = cycle
        self.update() # triggers paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(10, 10, 220, 220)
        
        # Background track
        pen_bg = QPen(QColor(BORDER))
        pen_bg.setWidth(12)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 0, 360 * 16)
        
        # Foreground progress arc
        pen_fg = QPen(QColor(self.color_state))
        pen_fg.setWidth(12)
        pen_fg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_fg)
        
        start_angle = 90 * 16
        span_angle = int(-360 * self.fraction * 16)
        painter.drawArc(rect, start_angle, span_angle)
        
        # Text
        painter.setPen(QColor(TXT_PRI))
        font_time = QFont(FONT_UI, 36, QFont.Weight.Bold)
        painter.setFont(font_time)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text_time)
        
        painter.setPen(QColor(TXT_SEC))
        font_state = QFont(FONT_UI, 12)
        painter.setFont(font_state)
        rect_state = QRectF(10, 140, 220, 30)
        painter.drawText(rect_state, Qt.AlignmentFlag.AlignCenter, self.text_state)

        # Draw 4 small cycle indicator circles at the bottom
        circle_radius = 4
        spacing = 12
        total_width = (4 * circle_radius * 2) + (3 * spacing)
        start_x = 10 + (220 - total_width) / 2
        y = 180
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(4):
            cx = start_x + i * (circle_radius * 2 + spacing)
            if i < min(self.cycle + 1, 4):
                painter.setBrush(QColor(GREEN))
            else:
                painter.setBrush(QColor(BORDER))
            painter.drawEllipse(QPoint(int(cx + circle_radius), y), circle_radius, circle_radius)

class CustomTitleBar(QFrame):
    def __init__(self, parent=None, title="Decipline"):
        super().__init__(parent)
        self.window = parent
        self.setObjectName("HeaderPanel")
        self.setFixedHeight(50)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        
        lbl_title = QLabel(title)
        lbl_title.setFont(QFont(FONT_UI, 14, QFont.Weight.Bold))
        layout.addWidget(lbl_title)
        
        lbl_sub = QLabel("Focus / Flow / Rest")
        lbl_sub.setFont(QFont(FONT_UI, 12))
        lbl_sub.setStyleSheet(f"color: {TXT_SEC};")
        layout.addWidget(lbl_sub)
        
        layout.addStretch()
        
        from .stats import check_streak
        streak = check_streak()
        lbl_streak = QLabel(f"🔥 {streak}")
        lbl_streak.setFont(QFont(FONT_UI, 12, QFont.Weight.Bold))
        if streak > 0:
            lbl_streak.setStyleSheet(f"color: {AMBER};")
        else:
            lbl_streak.setStyleSheet(f"color: {TXT_SEC};")
        layout.addWidget(lbl_streak)
        
        btn_settings = QPushButton("⚙️")
        btn_settings.setFlat(True)
        btn_settings.setFont(QFont(FONT_UI, 14))
        btn_settings.setStyleSheet(f"color: {TXT_SEC}; background: transparent; border: none;")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)
        
        btn_hide = QPushButton("Hide to Tray")
        btn_hide.setFlat(True)
        btn_hide.setStyleSheet(f"color: {TXT_SEC}; background: transparent;")
        btn_hide.clicked.connect(self.window.hide_to_tray)
        layout.addWidget(btn_hide)
        
        self._is_tracking = False
        self._start_pos = None

    def _open_settings(self):
        from .qt_settings import SettingsDialog
        dlg = SettingsDialog(self.window)
        if dlg.exec():
            # If settings changed, we might want to update the timer if it's IDLE
            if self.window.timer.state == PomodoroState.IDLE:
                self.window.timer.reset()

    # Native-feeling window drag without lagging the event queue
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(1000, 700)
        self.setMinimumSize(900, 600)
        
        # Central widget wrapper for border radius
        self.central = QFrame()
        self.central.setStyleSheet(f"QFrame {{ background-color: {BG}; border: 1px solid {BORDER}; border-radius: 12px; }}")
        self.setCentralWidget(self.central)
        
        main_layout = QVBoxLayout(self.central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Title Bar
        self.title_bar = CustomTitleBar(self)
        main_layout.addWidget(self.title_bar)
        
        # Content Area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(20)
        main_layout.addLayout(content_layout)
        
        # ── Schedule Panel (Left) ──
        schedule_panel = QVBoxLayout()
        
        lib_layout = QHBoxLayout()
        self.lbl_schedule_title = QLabel("Daily Routine")
        self.lbl_schedule_title.setFont(QFont(FONT_UI, 18, QFont.Weight.Bold))
        lib_layout.addWidget(self.lbl_schedule_title)
        
        from PyQt6.QtWidgets import QComboBox
        self.day_selector = QComboBox()
        self.day_selector.setStyleSheet(f"background-color: {PANEL_BG}; color: {TXT_PRI}; border: 1px solid {BORDER}; padding: 4px; border-radius: 4px;")
        self.day_selector.hide()
        self.day_selector.currentTextChanged.connect(self._on_day_changed)
        lib_layout.addWidget(self.day_selector)
        
        lib_layout.addStretch()
        
        btn_trends = QPushButton("📈 Trends")
        btn_trends.clicked.connect(self._open_trends)
        lib_layout.addWidget(btn_trends)
        
        btn_lib = QPushButton("📚 Library")
        btn_lib.clicked.connect(self._open_library)
        lib_layout.addWidget(btn_lib)
        
        schedule_panel.addLayout(lib_layout)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Task", "Duration", "Notes"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(2, 80)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.cellDoubleClicked.connect(self._edit_task)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background-color: {BG}; border: none; gridline-color: {BORDER}; }}
            QHeaderView::section {{ background-color: {PANEL_BG}; padding: 4px; border: 1px solid {BORDER}; }}
        """)
        schedule_panel.addWidget(self.table)
        
        content_layout.addLayout(schedule_panel, 3)
        
        # ── Timer Panel (Right) ──
        timer_panel = QVBoxLayout()
        timer_panel.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self.timer_widget = TimerWidget()
        timer_panel.addWidget(self.timer_widget)
        
        timer_controls = QHBoxLayout()
        self.btn_start = QPushButton("Start Focus")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_start.clicked.connect(self._toggle_timer)
        self.btn_reset = QPushButton("Reset")
        self.btn_reset.clicked.connect(self._reset_timer)
        self.btn_free = QPushButton("Free Timer")
        self.btn_free.clicked.connect(self._start_free_timer)
        timer_controls.addWidget(self.btn_start)
        timer_controls.addWidget(self.btn_reset)
        timer_controls.addWidget(self.btn_free)
        timer_panel.addLayout(timer_controls)
        
        self.btn_next_task = QPushButton("⏭️ Next Task")
        self.btn_next_task.clicked.connect(self._advance_task)
        self.btn_next_task.setStyleSheet(f"background-color: {CARD_BG}; font-weight: bold; padding: 10px;")
        timer_panel.addWidget(self.btn_next_task)
        
        self.btn_mark_complete = QPushButton("✅ Mark Complete")
        self.btn_mark_complete.setObjectName("PrimaryButton")
        self.btn_mark_complete.clicked.connect(self._mark_active_task_complete)
        self.btn_mark_complete.setStyleSheet("font-weight: bold; padding: 10px;")
        timer_panel.addWidget(self.btn_mark_complete)
        
        self.btn_reset_colors = QPushButton("🔄 Reset Colors")
        self.btn_reset_colors.clicked.connect(self._reset_colors)
        self.btn_reset_colors.setStyleSheet(f"background-color: {CARD_BG}; padding: 10px;")
        timer_panel.addWidget(self.btn_reset_colors)
        
        content_layout.addLayout(timer_panel, 2)
        
        # Pomodoro Logic
        self.timer = PomodoroTimer()
        self.signals = PomodoroSignals()
        
        self.timer.on_tick = self.signals.tick.emit
        self.timer.on_work_done = self.signals.work_done.emit
        self.timer.on_break_done = self.signals.break_done.emit
        self.timer.on_cycle_update = self.signals.cycle_update.emit
        self.timer.on_free_timer_done = self.signals.free_done.emit
        self.timer.on_task_completed = self.signals.task_completed.emit
        
        self.signals.tick.connect(self._on_tick)
        self.signals.work_done.connect(self._on_work_done)
        self.signals.break_done.connect(self._on_break_done)
        self.signals.free_done.connect(self._on_free_done)
        self.signals.task_completed.connect(self._on_task_completed)
        
        self._load_active_schedule()

    def hide_to_tray(self):
        self.hide()
        if self._on_hide:
            self._on_hide()

    def _open_library(self):
        from .qt_library import LibraryDialog
        dlg = LibraryDialog(self)
        dlg.exec()
        self._load_active_schedule()

    def _advance_task(self):
        from .storage import advance_task_index
        advance_task_index(getattr(self, 'current_day', None))
        self._refresh_table()

    def _mark_active_task_complete(self):
        day = getattr(self, 'current_day', None)
        active_idx = get_current_task_index(day)
        
        # Determine which task to mark: selected in table, or the active one
        selected_items = self.table.selectedItems()
        target_idx = selected_items[0].row() if selected_items else active_idx
        
        if target_idx >= 0:
            mark_task_completed(target_idx, day)
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
        dlg.exec()

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
                self.day_selector.addItems(list(sched.get("weekly_data", {}).keys()))
                self.day_selector.setCurrentText(sched.get("day"))
                self.day_selector.blockSignals(False)
                self.day_selector.show()
                self.current_day = sched.get("day")
            else:
                self.lbl_schedule_title.setText(sched.get("name", "Schedule"))
                self.day_selector.hide()
                
        self._refresh_table()

    def _refresh_table(self):
        sched = load_schedule(self.current_day) if hasattr(self, 'current_day') and self.current_day else load_schedule()
        if not sched:
            self.table.setRowCount(0)
            return
            
        rows = get_display_rows(sched)
        self.table.setRowCount(len(rows))
        
        active_index = get_current_task_index(getattr(self, 'current_day', None))
        
        for i, row in enumerate(rows):
            is_completed = row[4] if len(row) > 4 else False
            for j in range(4): # Only display first 4 columns
                val = row[j]
                item = QTableWidgetItem(str(val))
                if is_completed:
                    item.setForeground(QColor(GREEN))
                elif i < active_index:
                    item.setForeground(QColor(AMBER)) # Past task not completed
                elif i == active_index:
                    # Currently active task
                    item.setForeground(QColor("#0EA5E9")) # Sky blue
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setForeground(QColor(TXT_SEC))
                self.table.setItem(i, j, item)

    def _edit_task(self, row, col):
        sched = load_schedule(self.current_day) if hasattr(self, 'current_day') and self.current_day else load_schedule()
        if not sched or row >= len(sched.get("tasks", [])): return
        
        task = sched["tasks"][row]
        dlg = TaskDetailDialog(self, task, row, getattr(self, 'current_day', None))
        if dlg.exec():
            self._load_active_schedule()

    def _toggle_timer(self):
        if self.timer.is_running:
            self.timer.pause()
            self.btn_start.setText("Resume")
        else:
            self.timer.start()
            self.btn_start.setText("Pause")

    def _reset_timer(self):
        self.timer.reset()
        self.btn_start.setText("Start Focus")

    def _start_free_timer(self):
        from PyQt6.QtWidgets import QInputDialog
        mins, ok = QInputDialog.getInt(self, "Free Timer", "Minutes:", value=15, min=1, max=300)
        if ok and mins > 0:
            self.timer.start_free(mins * 60)
            self.btn_start.setText("Pause")

    def _on_tick(self, remaining, state):
        time_str = PomodoroTimer.fmt(remaining)
        # Calculate proper fraction based on current state
        total = self.timer._get_work_duration()
        if state == PomodoroState.SHORT_BREAK:
            total = self.timer._get_short_break()
        elif state == PomodoroState.LONG_BREAK:
            total = self.timer._get_long_break()
        elif state == PomodoroState.FREE_TIMER:
            total = self.timer._free_total
            
        fraction = remaining / total if total > 0 else 0
        
        color = GREEN
        state_str = "Focus Time"
        if state == PomodoroState.SHORT_BREAK:
            color = AMBER
            state_str = "Short Break"
        elif state == PomodoroState.LONG_BREAK:
            color = AMBER
            state_str = "Long Break"
        elif state == PomodoroState.FREE_TIMER:
            color = GREEN
            state_str = "Free Timer"
            
        self.timer_widget.update_state(fraction, time_str, state_str, color, cycle=self.timer.cycle)

    def _on_task_completed(self):
        from .stats import add_task_completed
        day = getattr(self, 'current_day', None)
        idx = get_current_task_index(day)
        if idx >= 0:
            mark_task_completed(idx, day)
            add_task_completed()
            
            # Auto advance to next task
            self._advance_task()

    def _on_work_done(self):
        self.btn_start.setText("Start Focus")
        
        # Bring window to front
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.activateWindow()
        
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Focus Session Complete")
        msg.setText("You finished 25 minutes of focus!\nDo you want to start your break now?")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.timer.begin_break()
            self.btn_start.setText("Pause")

    def _on_break_done(self):
        self.btn_start.setText("Start Focus")
        
        from .settings import load_settings
        settings = load_settings()
        
        # Play alarm sound
        if settings.get("sound_enabled", True):
            import winsound
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
            
        from .telegram_bot import notify_async
        notify_async("⏰ Break is over! Time to get back to work.")
        show_notification("Break Complete", "Time to get back to work!")
        
        # Ask to continue
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Break Complete")
        msg.setText("Your break is over!\nDo you want to continue focusing?")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.timer.start()
            self.btn_start.setText("Pause")
        
    def _on_free_done(self):
        self.btn_start.setText("Start Focus")
        from .telegram_bot import notify_async
        notify_async("⏰ Free Timer Complete! Your custom timer has finished.")
        show_notification("Free Timer Complete", "Your custom timer has finished!")
