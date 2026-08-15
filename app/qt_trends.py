"""
qt_trends.py - PyQt6 Trends and Statistics Dialog. Polished redesign.
"""

from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QWidget, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from .qt_style import *
from .stats import get_stats_summary


class TrendsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trends & Statistics")
        self.setMinimumSize(560, 620)
        self.setMaximumWidth(680)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.stats = get_stats_summary()
        self.history = self.stats.get("history", {})

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Title ────────────────────────────────────────────────────
        lbl_title = QLabel("Your Progress")
        lbl_title.setFont(QFont(FONT_UI, 17, QFont.Weight.Bold))
        root.addWidget(lbl_title)

        # ── Stat Pills ───────────────────────────────────────────────
        pills = QHBoxLayout()
        pills.setSpacing(10)

        total_secs = self.stats.get('study_seconds', 0)
        h = total_secs // 3600
        m = (total_secs % 3600) // 60
        pills.addWidget(self._pill(f"{h}h {m}m", "Total Focus", GREEN))
        pills.addWidget(self._pill(str(self.stats.get('tasks_completed', 0)), "Tasks Done", AMBER))
        pills.addWidget(self._pill(f"🔥 {self.stats.get('streak', 0)}", "Day Streak", "#FF9F0A"))
        root.addLayout(pills)

        # ── Chart Header ─────────────────────────────────────────────
        chart_hdr = QHBoxLayout()
        lbl_chart = QLabel("Focus Hours")
        lbl_chart.setFont(QFont(FONT_UI, 13, QFont.Weight.Bold))
        chart_hdr.addWidget(lbl_chart)
        chart_hdr.addStretch()

        self.range_combo = QComboBox()
        self.range_combo.addItems(["24 Hours", "Last Week", "Last Month", "Last Year", "All"])
        self.range_combo.setCurrentIndex(1)
        self.range_combo.setFixedWidth(130)
        self.range_combo.setFixedHeight(28)
        self.range_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 12px;
                color: {TXT_PRI};
            }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
            QComboBox QAbstractItemView {{
                background-color: {CARD_BG};
                border: 1px solid {BORDER};
                selection-background-color: {BORDER};
            }}
        """)
        self.range_combo.currentIndexChanged.connect(self._update_chart)
        chart_hdr.addWidget(self.range_combo)
        root.addLayout(chart_hdr)

        # ── Chart ────────────────────────────────────────────────────
        plt.rcParams.update({
            'font.family': 'Segoe UI',
            'axes.spines.top': False,
            'axes.spines.right': False,
        })
        self.figure, self.ax = plt.subplots(figsize=(5.5, 2.4))
        self.figure.patch.set_facecolor(BG)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setFixedHeight(190)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self.canvas)

        self._update_chart()

        # ── Divider ──────────────────────────────────────────────────
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f"background-color: {BORDER}; max-height: 1px;")
        root.addWidget(div)

        # ── Recent History ───────────────────────────────────────────
        lbl_hist = QLabel("Recent History")
        lbl_hist.setFont(QFont(FONT_UI, 13, QFont.Weight.Bold))
        root.addWidget(lbl_hist)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        hist_layout = QVBoxLayout(inner)
        hist_layout.setContentsMargins(0, 0, 0, 0)
        hist_layout.setSpacing(6)

        sorted_dates = sorted(self.history.keys(), reverse=True)[:14]  # max 14 rows

        if not sorted_dates:
            lbl_e = QLabel("No sessions recorded yet — start focusing!")
            lbl_e.setStyleSheet(f"color: {TXT_SEC}; font-size: 13px;")
            hist_layout.addWidget(lbl_e)
        else:
            for date_str in sorted_dates:
                data = self.history[date_str]
                h2 = data.get('study_seconds', 0) // 3600
                m2 = (data.get('study_seconds', 0) % 3600) // 60
                tasks = data.get('tasks', 0)

                row = QFrame()
                row.setStyleSheet(f"""
                    QFrame {{
                        background-color: {CARD_BG};
                        border-radius: 8px;
                        border: 1px solid {BORDER};
                    }}
                """)
                row.setFixedHeight(42)
                rl = QHBoxLayout(row)
                rl.setContentsMargins(12, 0, 12, 0)

                # Date
                lbl_d = QLabel(datetime.strptime(date_str, "%Y-%m-%d").strftime("%a, %d %b %Y"))
                lbl_d.setFont(QFont(FONT_UI, 11, QFont.Weight.Bold))
                lbl_d.setStyleSheet(f"color: {TXT_PRI}; background: transparent; border: none;")
                rl.addWidget(lbl_d)
                rl.addStretch()

                # Time badge
                time_badge = QLabel(f"⏱ {h2}h {m2}m")
                time_badge.setStyleSheet(f"""
                    background-color: {PANEL_BG}; color: {GREEN};
                    border-radius: 4px; padding: 2px 7px;
                    font-size: 11px; font-weight: bold; border: none;
                """)
                rl.addWidget(time_badge)

                # Task badge
                task_badge = QLabel(f"✅ {tasks}")
                task_badge.setStyleSheet(f"""
                    background-color: {PANEL_BG}; color: {AMBER};
                    border-radius: 4px; padding: 2px 7px;
                    font-size: 11px; font-weight: bold; border: none;
                    margin-left: 6px;
                """)
                rl.addWidget(task_badge)

                hist_layout.addWidget(row)

        hist_layout.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

    # ── Helpers ──────────────────────────────────────────────────────

    def _pill(self, value, label, color):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_BG};
                border-radius: 10px;
                border: 1px solid {BORDER};
            }}
        """)
        card.setFixedHeight(72)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)

        lv = QLabel(value)
        lv.setFont(QFont(FONT_UI, 16, QFont.Weight.Bold))
        lv.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        lv.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ll = QLabel(label)
        ll.setFont(QFont(FONT_UI, 10))
        ll.setStyleSheet(f"color: {TXT_SEC}; background: transparent; border: none;")
        ll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(lv)
        lay.addWidget(ll)
        return card

    def _update_chart(self):
        idx = self.range_combo.currentIndex()
        self.ax.clear()
        self.ax.set_facecolor(BG)
        self.figure.patch.set_facecolor(BG)

        today = datetime.today().date()

        if idx == 0:       # 24 Hours
            from .stats import load_stats
            raw = load_stats()
            day_hourly = raw.get("hourly", {}).get(today.strftime("%Y-%m-%d"), {})
            x = list(range(24))
            y = [day_hourly.get(str(h), 0) / 3600 for h in range(24)]
            tick_labels = [f"{h:02d}" for h in range(24)]
            self._render(x, y, tick_labels, step=4)
            self.ax.set_xlim(-0.5, 23.5)

        elif idx == 1:     # Last Week
            dates = [today - timedelta(days=i) for i in range(6, -1, -1)]
            y = [self.history.get(d.strftime("%Y-%m-%d"), {}).get("study_seconds", 0) / 3600 for d in dates]
            labels = [d.strftime("%d %b") for d in dates]
            self._render(list(range(7)), y, labels, step=1)
            self.ax.set_xlim(-0.5, 6.5)

        elif idx == 2:     # Last Month
            dates = [today - timedelta(days=i) for i in range(29, -1, -1)]
            y = [self.history.get(d.strftime("%Y-%m-%d"), {}).get("study_seconds", 0) / 3600 for d in dates]
            labels = [d.strftime("%d %b") for d in dates]
            self._render(list(range(30)), y, labels, step=5)
            self.ax.set_xlim(-0.5, 29.5)

        elif idx == 3:     # Last Year (weekly)
            dates = [today - timedelta(days=i) for i in range(364, -1, -1)]
            bucket_labels, y = self._weekly_buckets(dates)
            x = list(range(len(bucket_labels)))
            tick_labels = [d.strftime("%b") for d in bucket_labels]
            step = max(1, len(x) // 8)
            self._render(x, y, tick_labels, step=step)
            if x: self.ax.set_xlim(-0.5, len(x) - 0.5)

        else:              # All Time (monthly)
            if not self.history:
                self._render([], [], [], step=1)
            else:
                first = datetime.strptime(sorted(self.history.keys())[0], "%Y-%m-%d").date()
                dates = [first + timedelta(days=i) for i in range((today - first).days + 1)]
                bucket_labels, y = self._monthly_buckets(dates)
                x = list(range(len(bucket_labels)))
                tick_labels = [d.strftime("%b '%y") for d in bucket_labels]
                step = max(1, len(x) // 8)
                self._render(x, y, tick_labels, step=step)
                if x: self.ax.set_xlim(-0.5, len(x) - 0.5)

        # Shared styling
        self.ax.set_ylabel("hrs", color=TXT_SEC, fontsize=8, labelpad=4)
        self.ax.tick_params(axis='y', colors=TXT_SEC, labelsize=7, length=0)
        self.ax.tick_params(axis='x', colors=TXT_SEC, length=0)
        self.ax.spines['left'].set_visible(False)
        self.ax.spines['bottom'].set_edgecolor(BORDER)
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        self.ax.grid(axis='y', color=BORDER, linestyle='--', alpha=0.35, zorder=0)
        self.ax.set_ylim(bottom=0)
        self.figure.tight_layout(pad=0.6)
        self.canvas.draw()

    def _render(self, x, y, tick_labels, step=1):
        if not x or not any(v > 0 for v in y):
            self.ax.text(0.5, 0.5, "No data yet — start a Pomodoro!",
                         transform=self.ax.transAxes, ha='center', va='center',
                         color=TXT_SEC, fontsize=10)
            return

        # Gradient-style bars using alpha steps
        self.ax.bar(x, y, color=AMBER, alpha=0.75, width=0.55, zorder=3)

        # Smooth line on top
        self.ax.plot(x, y, color="#FBBF24", linewidth=1.8, zorder=4,
                     marker='o', markersize=2.5, markerfacecolor="#FBBF24",
                     markeredgewidth=0)

        # Highlight peak bar
        if y:
            peak = max(y)
            peak_idx = y.index(peak)
            self.ax.bar([x[peak_idx]], [peak], color="#FBBF24", alpha=1.0, width=0.55, zorder=3)

        self.ax.set_xticks(x[::step])
        self.ax.set_xticklabels(tick_labels[::step], rotation=30, ha='right',
                                 fontsize=7.5, color=TXT_SEC)

    def _weekly_buckets(self, date_range):
        week_data, week_order = {}, []
        for d in date_range:
            monday = d - timedelta(days=d.weekday())
            key = monday.strftime("%Y-%m-%d")
            if key not in week_data:
                week_data[key] = 0
                week_order.append(monday)
            week_data[key] += self.history.get(d.strftime("%Y-%m-%d"), {}).get("study_seconds", 0) / 3600
        return week_order, [week_data[d.strftime("%Y-%m-%d")] for d in week_order]

    def _monthly_buckets(self, date_range):
        month_data, month_order = {}, []
        for d in date_range:
            key = d.strftime("%Y-%m")
            if key not in month_data:
                month_data[key] = 0
                month_order.append(datetime.strptime(key, "%Y-%m").date())
            month_data[key] += self.history.get(d.strftime("%Y-%m-%d"), {}).get("study_seconds", 0) / 3600
        return month_order, [month_data[d.strftime("%Y-%m")] for d in month_order]
