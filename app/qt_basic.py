"""One compact Pomodoro controller, shared by Basic and Expert workspaces."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QSpinBox, QPushButton, QInputDialog, QMessageBox, QCheckBox
from . import stats
from .settings import load_settings
from .pomodoro import PomodoroState as State, PomodoroTimer
from .qt_components import label
from .qt_style import TXT_PRI, TXT_SEC, AMBER, GREEN, BORDER

_KEEP_SELECTION = object()


def duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m {seconds:02d}s" if seconds else f"{minutes}m"


class CycleSelector(QWidget):
    def __init__(self, choose, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch()
        self.buttons = []
        for index in range(4):
            button = QPushButton("●")
            button.setCheckable(True)
            button.setFixedSize(30, 30)
            button.setAccessibleName(f"Select Pomodoro cycle {index + 1}")
            button.setToolTip(f"Cycle {index + 1} · choose and start a fresh focus session")
            button.clicked.connect(lambda checked, i=index: choose(i))
            row.addWidget(button)
            self.buttons.append(button)
        row.addStretch()

    def select(self, index):
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)
        if getattr(self, "_selected", None) == index:
            return
        self._selected = index
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)
            button.setStyleSheet(
                f"padding: 0; border-radius: 15px; font-size: 15px; "
                f"color: {GREEN if i == index else TXT_SEC}; "
                f"background: {'#213A35' if i == index else 'transparent'}; "
                f"border: 1px solid {GREEN if i == index else BORDER};")


class BasicPanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._saved_message = None
        self._ready = False
        self._courses = {}
        self.setStyleSheet("QPushButton { padding: 6px 10px; } QComboBox, QSpinBox { padding: 5px 8px; }")
        content = QVBoxLayout(self)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(7)
        top = QHBoxLayout()
        top.addWidget(label("Focus", "SectionTitle"))
        top.addStretch()
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 120)
        self.minutes.setSuffix(" min")
        self.minutes.setAccessibleName("Focus duration in minutes")
        self.minutes.setValue(load_settings().get("focus_time", 25))
        self.minutes.setFixedWidth(104)
        self.minutes.valueChanged.connect(self.sync)
        top.addWidget(self.minutes)
        content.addLayout(top)
        self.path_row = QWidget()
        path = QHBoxLayout(self.path_row)
        path.setContentsMargins(0, 0, 0, 0)
        self.course_path_checkbox = QCheckBox("Course path")
        self.course_path_checkbox.setAccessibleName("Use course path instead of schedule path")
        self.course_path_checkbox.setToolTip("Checked: track a course. Unchecked: complete schedule tasks when focus ends. Changing path saves the current session.")
        self.course_path_checkbox.toggled.connect(window.set_expert_course_path)
        path.addWidget(self.course_path_checkbox)
        path.addStretch()
        path.addWidget(label("Off: schedule", "MetricLabel"))
        content.addWidget(self.path_row)
        self.course_heading = QWidget()
        course_heading = QHBoxLayout(self.course_heading)
        course_heading.setContentsMargins(0, 0, 0, 0)
        course_heading.addWidget(label("COURSE", "MetricLabel"))
        course_heading.addStretch()
        self.manage_btn = QPushButton("Manage")
        self.manage_btn.setObjectName("QuietButton")
        self.manage_btn.setStyleSheet("padding: 0 4px; font-size: 11px;")
        self.manage_btn.setAccessibleName("Manage courses and lectures")
        self.manage_btn.clicked.connect(self._manage_courses)
        course_heading.addWidget(self.manage_btn)
        content.addWidget(self.course_heading)
        self.course_row = QWidget()
        row = QHBoxLayout(self.course_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.course = QComboBox()
        self.course.setMinimumWidth(0)
        self.course.setMinimumContentsLength(12)
        self.course.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.course.setAccessibleName("Course to credit with study time")
        self.course.currentIndexChanged.connect(self._course_changed)
        row.addWidget(self.course, 1)
        self.new_course = QPushButton("+")
        self.new_course.setFixedWidth(32)
        self.new_course.setAccessibleName("Add course")
        self.new_course.setToolTip("Add a course")
        self.new_course.clicked.connect(self._add_course)
        row.addWidget(self.new_course)
        content.addWidget(self.course_row)
        self.course_hours = label("", "MetricLabel")
        self.lecture_toggle = QPushButton("Lecture ▸")
        self.lecture_toggle.setObjectName("QuietButton")
        self.lecture_toggle.setCheckable(True)
        self.lecture_toggle.toggled.connect(self._show_lectures)
        self.course_info = QWidget()
        course_info = QHBoxLayout(self.course_info)
        course_info.setContentsMargins(0, 0, 0, 0)
        course_info.addWidget(self.course_hours, 1)
        course_info.addWidget(self.lecture_toggle)
        content.addWidget(self.course_info)
        self.schedule_context = label("", "SectionTitle")
        self.schedule_context.setWordWrap(True)
        self.schedule_context.setMaximumHeight(76)
        content.addWidget(self.schedule_context)
        self.lecture_fields = QWidget()
        lecture_row = QHBoxLayout(self.lecture_fields)
        lecture_row.setContentsMargins(0, 0, 0, 0)
        self.lecture = QComboBox()
        self.lecture.setMinimumWidth(0)
        self.lecture.setMinimumContentsLength(12)
        self.lecture.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.lecture.setAccessibleName("Optional lecture")
        self.lecture.currentIndexChanged.connect(self._context_changed)
        self.new_lecture = QPushButton("+")
        self.new_lecture.setFixedWidth(32)
        self.new_lecture.setAccessibleName("Add lecture")
        self.new_lecture.setToolTip("Add a lecture to this course")
        self.new_lecture.clicked.connect(self._add_lecture)
        lecture_row.addWidget(self.lecture, 1)
        lecture_row.addWidget(self.new_lecture)
        content.addWidget(self.lecture_fields)
        self.lecture_fields.hide()
        content.addSpacing(4)
        self.status = label("Ready", "Muted")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(self.status)
        self.clock = label("25:00")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock.setMinimumHeight(62)
        content.addWidget(self.clock)
        self.cycles = CycleSelector(self._select_cycle)
        content.addWidget(self.cycles)
        self.cycle_label = label("Cycle 1 of 4 · long break after cycle 4", "MetricLabel")
        self.cycle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cycle_label.setWordWrap(True)
        content.addWidget(self.cycle_label)
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self._toggle)
        content.addWidget(self.start_btn)
        row = QHBoxLayout()
        self.break_btn = QPushButton("Take a break")
        self.break_btn.clicked.connect(self._break)
        self.stop_btn = QPushButton("Stop & save")
        self.stop_btn.clicked.connect(self._stop)
        row.addWidget(self.break_btn, 1)
        row.addWidget(self.stop_btn, 1)
        content.addLayout(row)
        self.session = label("Breaks are saved separately from study.", "MetricLabel")
        self.session.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session.setWordWrap(True)
        content.addWidget(self.session)
        self.history_btn = QPushButton("View trends")
        self.history_btn.setObjectName("QuietButton")
        self.history_btn.clicked.connect(window._open_trends)
        content.addWidget(self.history_btn)
        window.signals.tick.connect(self.sync)
        window.signals.work_done.connect(self.sync)
        window.signals.break_done.connect(self.sync)
        window.signals.cycle_update.connect(self.sync)
        window.signals.free_done.connect(self.sync)
        window.signals.stats_saved.connect(self._stats_updated)
        self._ready = True
        self.reload_courses()

    def reload_courses(self, cid=_KEEP_SELECTION, lid=_KEEP_SELECTION):
        previous = self.course.currentData()
        cid = previous if cid is _KEEP_SELECTION else cid
        if lid is _KEEP_SELECTION:
            lid = self.lecture.currentData() if cid == previous else None
        self._courses = stats.get_courses()
        self.course.blockSignals(True)
        self.course.clear()
        self.course.addItem("General study", None)
        for key, course in self._courses.items():
            self.course.addItem(course["name"], key)
        self.course.setCurrentIndex(max(0, self.course.findData(cid)))
        self.course.blockSignals(False)
        self._course_changed()
        if lid is not None:
            self.lecture.setCurrentIndex(max(0, self.lecture.findData(lid)))
            self.lecture_toggle.setChecked(True)

    def _show_lectures(self, show):
        self.lecture_fields.setVisible(show and self.course.currentData() is not None and self.window.uses_course_path)
        self.lecture_toggle.setText("Lecture ▾" if show else "Lecture ▸")

    def _course_changed(self):
        self.lecture.blockSignals(True)
        self.lecture.clear()
        self.lecture.addItem("Whole course · no lecture selected", None)
        course = self._courses.get(self.course.currentData(), {})
        for lid, lecture in course.get("lectures", {}).items():
            self.lecture.addItem(lecture["name"], lid)
        self.lecture.blockSignals(False)
        self._show_lectures(self.lecture_toggle.isChecked())
        self._context_changed()

    def _context_changed(self):
        if not self._ready:
            return
        if not self.window.timer.session_id and self.window.uses_course_path:
            self.window.timer.set_context(self.course.currentData(), self.lecture.currentData())
        self._saved_message = None
        self.sync()

    def _add_course(self):
        text, ok = QInputDialog.getText(self, "Add a course", "Course name:")
        if ok and text.strip():
            try:
                self.reload_courses(stats.create_course(text))
            except (ValueError, OSError) as error:
                QMessageBox.warning(self, "Could not add course", str(error))

    def _add_lecture(self):
        cid = self.course.currentData()
        if cid is not None:
            text, ok = QInputDialog.getText(self, "Add a lecture", "Lecture name:")
            if ok and text.strip():
                try:
                    self.reload_courses(cid, stats.create_lecture(cid, text))
                except (ValueError, OSError) as error:
                    QMessageBox.warning(self, "Could not add lecture", str(error))

    def _manage_courses(self):
        from .qt_courses import CourseManagerDialog
        timer = self.window.timer
        protected = (timer.course_id, timer.lecture_id) if timer.session_id else (None, None)
        dialog = CourseManagerDialog(self, self.course.currentData(), self.lecture.currentData(), protected)
        dialog.exec()
        dialog.deleteLater()
        self.reload_courses()

    def _select_cycle(self, index):
        self.window.timer.select_cycle(index)
        self._saved_message = "Cycle selected. Press Start when ready."
        self.sync()

    def _toggle(self):
        self._saved_message = None
        timer = self.window.timer
        if timer.is_running:
            timer.pause()
        elif timer.state == State.WAITING_FOR_BREAK:
            timer.begin_break()
        else:
            self.window.start_focus(self.minutes.value() * 60)
        self.sync()

    def _break(self):
        self._saved_message = None
        timer = self.window.timer
        effective = timer._resume_state if timer.state == State.PAUSED else timer.state
        if effective in (State.SHORT_BREAK, State.LONG_BREAK):
            timer.end_break()
        else:
            timer.take_break()
        self.sync()

    def _stop(self):
        self.window.timer.reset()
        self._saved_message = "Progress saved. Ready when you are."
        self.sync()

    def _stats_updated(self, courses):
        for cid, course in courses.items():
            existing = self._courses.get(cid)
            if existing is None:
                continue
            # A queued progress update must not undo a later rename/removal.
            for key in ("study_seconds", "break_seconds"):
                existing[key] = course.get(key, 0)
            existing["totals"] = dict(course["totals"])
            for lid, lecture in course.get("lectures", {}).items():
                if lid in existing["lectures"]:
                    for key in ("study_seconds", "break_seconds"):
                        existing["lectures"][lid][key] = lecture.get(key, 0)
        self.sync()

    def sync(self, *_):
        if not self._ready:
            return
        timer = self.window.timer
        state = timer.state
        effective = timer._resume_state if state == State.PAUSED else state
        on_break = effective in (State.SHORT_BREAK, State.LONG_BREAK)
        free = effective == State.FREE_TIMER
        locked = timer.session_id is not None or free
        course_path = self.window.uses_course_path
        self.path_row.setVisible(self.window.experience_mode == "expert")
        self.course_path_checkbox.blockSignals(True)
        self.course_path_checkbox.setChecked(course_path)
        self.course_path_checkbox.blockSignals(False)
        for widget in (self.course_heading, self.course_row, self.course_info):
            widget.setVisible(course_path)
        self.lecture_fields.setVisible(course_path and self.lecture_toggle.isChecked() and self.course.currentData() is not None)
        self.schedule_context.setVisible(not course_path)
        target = timer.focus_context
        task_name = target["text"] if target else self.window.schedule_focus_name
        self.schedule_context.setText(f"Schedule · {task_name}")
        for field in (self.course, self.lecture, self.new_course, self.new_lecture, self.minutes):
            field.setEnabled(not locked)
        self.new_lecture.setEnabled(not locked and self.course.currentData() is not None)
        self.lecture_toggle.setVisible(self.course.currentData() is not None)
        idle = state in (State.IDLE, State.WAITING_FOR_WORK)
        self.clock.setText(PomodoroTimer.fmt(self.minutes.value() * 60 if idle else timer.remaining))
        self.clock.setStyleSheet(f"font-size: 48px; font-weight: 600; color: {AMBER if on_break else TXT_PRI};")
        self.cycles.select(timer.selected_cycle)
        self.cycle_label.setText(f"Cycle {timer.selected_cycle + 1} of 4 · long break after cycle 4")
        self.start_btn.setText("Pause" if timer.is_running else "Resume" if state == State.PAUSED
                               else "Start break" if state == State.WAITING_FOR_BREAK else "Start")
        self.start_btn.setEnabled(course_path or locked or self.window.schedule_focus_available)
        self.stop_btn.setVisible(locked)
        self.break_btn.setVisible(locked and not free and state != State.WAITING_FOR_BREAK)
        self.break_btn.setText("End break" if on_break else "Take a break")
        self.status.setText("Paused · break" if state == State.PAUSED and on_break else
                            "Paused" if state == State.PAUSED else
                            "Break · study time is paused" if on_break else
                            "Free timer" if free else "Focusing" if timer.is_running else
                            "Focus complete · ready for a break" if state == State.WAITING_FOR_BREAK else
                            self._saved_message or "Ready when you are")
        self.session.setText("Free timer · not added to study history." if free else
                             "Schedule path · task completes when focus ends.\nBreaks are saved separately." if not course_path else
                             "Breaks are saved separately from study.")
        selected = self._courses.get(self.course.currentData())
        self.course_hours.setText(f"{duration(stats.course_totals(selected)['study_seconds'])} studied"
                                  if selected else "Track your time by course.")
        self.course.setToolTip(self.course.currentText())
        self.lecture.setToolTip(self.lecture.currentText())
