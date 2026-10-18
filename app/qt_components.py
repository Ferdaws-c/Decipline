"""Small shared presentation components; no animations or graphics effects."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QScrollArea
from .qt_style import TXT_SEC


def label(text, role="Muted"):
    widget = QLabel(text)
    widget.setObjectName(role)
    return widget


def card():
    frame = QFrame()
    frame.setObjectName("SurfaceCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(14)
    return frame, layout


def metric(title, value="—", color=None):
    frame = QFrame()
    frame.setObjectName("MetricCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(4)
    layout.addWidget(label(title, "MetricLabel"))
    number = label(value, "MetricValue")
    if color:
        number.setStyleSheet(f"color: {color};")
    layout.addWidget(number)
    return frame, number


def prepare_table(table, row_height=44):
    table.setShowGrid(False)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setDefaultSectionSize(row_height)
    table.verticalHeader().hide()
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    table.horizontalHeader().setHighlightSections(False)
    table.setFrameShape(QFrame.Shape.NoFrame)


def scroll_page(widget, minimum_height=670):
    widget.setMinimumHeight(minimum_height)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll
