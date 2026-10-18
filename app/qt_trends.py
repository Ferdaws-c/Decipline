"""A lightweight native study evaluation; opening Trends needs no plotting runtime."""
import math
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                            QPushButton, QTableView, QHeaderView, QToolTip)
from .qt_style import BG, PANEL_BG, BORDER, TXT_PRI, TXT_SEC, GREEN, ACCENT, FONT_UI
from .qt_components import label, card, metric, prepare_table
from .qt_basic import duration
from .stats import get_stats_summary, course_totals
from .analytics import evaluate


class StudyChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self.series = []
        self.bucket = "day"
        self.undated = 0
        self._hits = []
        self.setAccessibleName("Study time chart. Exact values are available by hovering each bar.")

    def set_data(self, evaluation):
        self.series, self.bucket = evaluation["series"], evaluation["bucket"]
        self.undated = evaluation["undated_study"]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont(FONT_UI, 9))
        plot = QRectF(58, 12, max(1, self.width() - 76), max(1, self.height() - 45))
        peak = max((v for _, v in self.series), default=0)
        self._hits = []
        if not peak:
            painter.setPen(QColor(TXT_SEC))
            message = ("Earlier study is included in your totals.\nNew sessions will appear on this chart." if self.undated else
                       "Your study time will appear here.\nChoose a course and start a focus session.")
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)
            return
        step = 300 if peak <= 3600 else 1800 if peak <= 14400 else 3600
        top = max(step * 4, math.ceil(peak / (step * 4)) * step * 4)
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            painter.setPen(QPen(QColor(BORDER), 1))
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            painter.setPen(QColor(TXT_SEC))
            painter.drawText(QRectF(0, y - 10, 49, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             duration(top * i / 4))
        width = plot.width() / max(1, len(self.series))
        stride = max(1, math.ceil(len(self.series) / 7))
        for i, (day, seconds) in enumerate(self.series):
            x = plot.left() + i * width
            bar = QRectF(x + width * .22, plot.bottom() - seconds / top * plot.height(),
                         max(2, width * .56), seconds / top * plot.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(GREEN))
            if seconds:
                painter.drawRoundedRect(bar, min(4, bar.width() / 3), min(4, bar.height() / 3))
            self._hits.append((QRectF(x, plot.top(), width, plot.height()), day, seconds))
            if i % stride == 0:
                painter.setPen(QColor(TXT_SEC))
                text = day.strftime("%b %d" if self.bucket in ("day", "week") else "%b %y" if self.bucket == "month" else "%Y")
                painter.drawText(QRectF(x - 17, plot.bottom() + 7, width + 34, 22), Qt.AlignmentFlag.AlignHCenter, text)

    def mouseMoveEvent(self, event):
        for rect, day, seconds in self._hits:
            if rect.contains(event.position()):
                prefix = "Week of " if self.bucket == "week" else ""
                QToolTip.showText(event.globalPosition().toPoint(), f"{prefix}{day:%d %b %Y}\n{duration(seconds)} studied", self)
                return
        QToolTip.hideText()


class TrendsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Study trends")
        self.resize(800, 700)
        self.setMinimumSize(680, 660)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)
        heading = QHBoxLayout()
        heading.addWidget(label("Your study, at a glance.", "PageTitle"))
        heading.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        heading.addWidget(close)
        root.addLayout(heading)
        filters = QHBoxLayout()
        self.course_combo = QComboBox()
        self.course_combo.setAccessibleName("Filter trends by course")
        self.course_combo.setMinimumWidth(160)
        self.range_combo = QComboBox()
        self.range_combo.setAccessibleName("Study evaluation period")
        for title, days in (("Today", 1), ("Last 7 days", 7), ("Last 30 days", 30), ("Last 365 days", 365), ("All time", None)):
            self.range_combo.addItem(title, days)
        self.range_combo.setCurrentIndex(1)
        filters.addWidget(self.course_combo, 1)
        filters.addWidget(self.range_combo)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        filters.addWidget(refresh)
        root.addLayout(filters)
        metrics = QHBoxLayout()
        self.values = {}
        for key, title, color in (("study_seconds", "STUDIED", GREEN), ("pomodoros", "POMODOROS", ACCENT),
                                  ("active_days", "DAYS STUDIED", None), ("break_seconds", "BREAKS", None)):
            frame, value = metric(title, "0", color)
            self.values[key] = value
            metrics.addWidget(frame)
        root.addLayout(metrics)
        chart_card, chart_layout = card()
        chart_card.setMinimumHeight(220)
        chart_layout.setContentsMargins(16, 12, 16, 10)
        chart_layout.setSpacing(4)
        self.chart_title = label("Daily study time", "SectionTitle")
        chart_layout.addWidget(self.chart_title)
        self.chart = StudyChart()
        chart_layout.addWidget(self.chart, 1)
        self.insight = label("")
        self.insight.setWordWrap(True)
        chart_layout.addWidget(self.insight)
        root.addWidget(chart_card, 1)
        self.breakdown_title = label("Time by course", "SectionTitle")
        root.addWidget(self.breakdown_title)
        self.model = QStandardItemModel(0, 4, self)
        self.model.setHorizontalHeaderLabels(["Course", "Study hours", "Breaks", "Pomodoros"])
        self.table = QTableView()
        self.table.setModel(self.model)
        prepare_table(self.table, row_height=36)
        self.table.setMinimumHeight(110)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column, width in ((1, 120), (2, 100), (3, 100)):
            self.table.setColumnWidth(column, width)
        root.addWidget(self.table)
        self.note = label("Breaks are excluded from study hours. Pomodoros count only when the focus countdown finishes.", "MetricLabel")
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        self.course_combo.currentIndexChanged.connect(self._update_chart)
        self.range_combo.currentIndexChanged.connect(self._update_chart)
        self.refresh()

    def refresh(self, *_):
        self.stats = get_stats_summary()
        cid = self.course_combo.currentData()
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        self.course_combo.addItem("All courses + general study", None)
        recorded = {s.get("course_id") for s in self.stats.get("lecture_sessions", {}).values()
                    if s.get("study_seconds") or s.get("break_seconds") or s.get("completed_at")}
        for key, course in self.stats.get("courses", {}).items():
            if course.get("deleted") and not any(course_totals(course).values()) and key not in recorded:
                continue
            self.course_combo.addItem(course["name"] + (" (removed)" if course.get("deleted") else ""), key)
        self.course_combo.setCurrentIndex(max(0, self.course_combo.findData(cid)))
        self.course_combo.blockSignals(False)
        self._update_chart()

    def _update_chart(self, *_):
        if not hasattr(self, "stats"):
            return
        result = evaluate(self.stats, self.range_combo.currentData(), self.course_combo.currentData())
        self.evaluation = result
        for key, widget in self.values.items():
            widget.setText(duration(result[key]) if key.endswith("seconds") else str(result[key]))
        titles = {"day": "Daily study time", "week": "Weekly study time", "month": "Monthly study time", "year": "Yearly study time"}
        self.chart_title.setText(titles[result["bucket"]])
        self.chart.set_data(result)
        self.insight.setText(f"{duration(result['average'])} per day studied · {result['active_days']} days with focus time"
                             if result["active_days"] else "Small sessions add up. Start with one focus session.")
        if result["undated_study"]:
            self.insight.setText(f"{duration(result['undated_study'])} of earlier study has no date and is included in the totals.")
        self.model.removeRows(0, self.model.rowCount())
        course_selected = self.course_combo.currentData() is not None
        self.breakdown_title.setText("Time by lecture" if course_selected else "Time by course")
        self.model.setHorizontalHeaderLabels(["Lecture" if course_selected else "Course", "Study hours", "Breaks", "Pomodoros"])
        for cid, row in result["lectures"] if course_selected else result["courses"]:
            items = [QStandardItem(row["name"]), QStandardItem(f"{row['study_seconds'] / 3600:.2f} h"),
                     QStandardItem(duration(row["break_seconds"])), QStandardItem(str(row["pomodoros"]))]
            items[1].setToolTip(f"{duration(row['study_seconds'])} · {int(row['study_seconds'])} seconds")
            for item in items[1:]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.model.appendRow(items)
