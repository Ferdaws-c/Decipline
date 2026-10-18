"""Schedule table data without allocating four Qt items for every task."""

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QBrush, QColor, QFont

from .qt_style import GREEN, AMBER, TXT_SEC, ACCENT


class ScheduleTableModel(QAbstractTableModel):
    HEADERS = ("Time", "Task", "Duration", "Notes")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = []
        self._active_index = None
        self._completed = QBrush(QColor(GREEN))
        self._past = QBrush(QColor(AMBER))
        self._active = QBrush(QColor(ACCENT))
        self._active_bg = QBrush(QColor("#262438"))
        self._future = QBrush(QColor(TXT_SEC))
        self._bold = QFont()
        self._bold.setBold(True)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section] if 0 <= section < len(self.HEADERS) else None
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        completed = len(row) > 4 and row[4]
        active = self._active_index
        if role == Qt.ItemDataRole.DisplayRole:
            return str(row[index.column()])
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(row[index.column()])
        if role == Qt.ItemDataRole.BackgroundRole and not completed and index.row() == active:
            return self._active_bg
        if role == Qt.ItemDataRole.ForegroundRole:
            if completed:
                return self._completed
            if active is not None and index.row() < active:
                return self._past
            return self._active if index.row() == active else self._future
        if role == Qt.ItemDataRole.FontRole and not completed and index.row() == active:
            return self._bold
        return None

    def set_rows(self, rows, active_index=None):
        if len(rows) != len(self._rows):
            self.beginResetModel()
            self._rows = rows
            self._active_index = active_index
            self.endResetModel()
            return
        changed = [i for i, (old, new) in enumerate(zip(self._rows, rows)) if old != new]
        if active_index != self._active_index:
            indices = [i for i in (active_index, self._active_index) if i is not None]
            if indices:
                changed.extend(range(max(0, min(indices)), min(len(rows), max(indices) + 1)))
        self._rows = rows
        self._active_index = active_index
        if changed:
            self.dataChanged.emit(self.index(min(changed), 0), self.index(max(changed), 3), [])
