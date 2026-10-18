"""Course and lecture CRUD with restorable removal and preserved study history."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                            QPushButton, QListWidget, QListWidgetItem,
                            QCheckBox, QInputDialog, QMessageBox)
from . import stats
from .qt_components import label
from .qt_basic import duration


class CourseManagerDialog(QDialog):
    def __init__(self, parent=None, course_id=None, lecture_id=None, protected_context=(None, None)):
        super().__init__(parent)
        self.protected_context = protected_context
        self.setWindowTitle("Manage courses and lectures")
        self.resize(640, 570)
        self.setMinimumSize(560, 530)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(12)
        root.addWidget(label("Your courses & lectures", "PageTitle"))
        hint = label("Add, rename or remove items. Your recorded study history stays in Trends.")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.show_removed = QCheckBox("Show removed items")
        self.show_removed.toggled.connect(lambda: self.reload(self.course.currentData(), self._lecture_id()))
        root.addWidget(self.show_removed)
        root.addWidget(label("Course", "SectionTitle"))
        row = QHBoxLayout()
        self.course = QComboBox()
        self.course.setMinimumContentsLength(15)
        self.course.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.course.setAccessibleName("Course to manage")
        self.course.currentIndexChanged.connect(self._course_changed)
        row.addWidget(self.course, 1)
        self.add_course_btn = self._button("Add course", self._add_course)
        row.addWidget(self.add_course_btn)
        root.addLayout(row)
        row = QHBoxLayout()
        self.rename_course_btn = self._button("Rename course", self._rename_course)
        self.remove_course_btn = self._button("Remove course", self._remove_course, "DangerButton")
        self.restore_course_btn = self._button("Restore course", self._restore_course, "SuccessButton")
        for button in (self.rename_course_btn, self.remove_course_btn, self.restore_course_btn):
            row.addWidget(button)
        row.addStretch()
        root.addLayout(row)
        self.course_total = label("")
        root.addWidget(self.course_total)
        root.addWidget(label("Lectures", "SectionTitle"))
        self.lectures = QListWidget()
        self.lectures.setAccessibleName("Lectures in the selected course")
        self.lectures.setStyleSheet("QListWidget::item { padding: 8px; margin: 2px; }")
        self.lectures.itemSelectionChanged.connect(self._update_actions)
        self.lectures.itemDoubleClicked.connect(self._rename_lecture)
        root.addWidget(self.lectures, 1)
        row = QHBoxLayout()
        self.add_lecture_btn = self._button("Add lecture", self._add_lecture)
        self.rename_lecture_btn = self._button("Rename", self._rename_lecture)
        self.remove_lecture_btn = self._button("Remove", self._remove_lecture, "DangerButton")
        self.restore_lecture_btn = self._button("Restore", self._restore_lecture, "SuccessButton")
        for button in (self.add_lecture_btn, self.rename_lecture_btn, self.remove_lecture_btn, self.restore_lecture_btn):
            row.addWidget(button)
        row.addStretch()
        root.addLayout(row)
        self.notice = label("")
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        row = QHBoxLayout()
        row.addStretch()
        close = self._button("Close", self.accept)
        row.addWidget(close)
        root.addLayout(row)
        self.reload(course_id, lecture_id)

    @staticmethod
    def _button(text, callback, role=None):
        button = QPushButton(text)
        if role:
            button.setObjectName(role)
        button.clicked.connect(callback)
        return button

    def _lecture_id(self):
        item = self.lectures.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def reload(self, cid=None, lid=None):
        self._courses = stats.get_courses(include_removed=True)
        self.course.blockSignals(True)
        self.course.clear()
        for key, course in self._courses.items():
            if self.show_removed.isChecked() or not course.get("deleted"):
                self.course.addItem(course["name"] + (" (removed)" if course.get("deleted") else ""), key)
        if not self.course.count():
            self.course.addItem("Add your first course", None)
        self.course.setCurrentIndex(max(0, self.course.findData(cid)))
        self.course.blockSignals(False)
        self._course_changed()
        for index in range(self.lectures.count()):
            item = self.lectures.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == lid:
                self.lectures.setCurrentItem(item)
                break

    def _course_changed(self, *_):
        self.lectures.clear()
        course = self._courses.get(self.course.currentData(), {})
        totals = stats.course_totals(course)
        self.course_total.setText(f"Study: {duration(totals['study_seconds'])} · Breaks: {duration(totals['break_seconds'])}"
                                  if course else "Add a course to start organizing your lectures.")
        for lid, lecture in course.get("lectures", {}).items():
            if lecture.get("deleted") and not self.show_removed.isChecked():
                continue
            suffix = " (removed)" if lecture.get("deleted") else ""
            text = f"{lecture['name']}{suffix}  ·  {duration(lecture.get('study_seconds', 0))} studied"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, lid)
            item.setToolTip(text)
            self.lectures.addItem(item)
        self.lectures.setCurrentRow(0 if self.lectures.count() else -1)
        self._update_actions()

    def _update_actions(self):
        cid, lid = self.course.currentData(), self._lecture_id()
        course = self._courses.get(cid)
        lecture = course.get("lectures", {}).get(lid) if course else None
        course_removed = bool(course and course.get("deleted"))
        lecture_removed = bool(lecture and lecture.get("deleted"))
        protected_course = cid is not None and cid == self.protected_context[0]
        protected_lecture = protected_course and lid is not None and lid == self.protected_context[1]
        self.rename_course_btn.setEnabled(course is not None)
        self.remove_course_btn.setEnabled(course is not None and not course_removed and not protected_course)
        self.remove_course_btn.setVisible(not course_removed)
        self.restore_course_btn.setVisible(course_removed)
        self.restore_course_btn.setEnabled(course_removed)
        self.add_lecture_btn.setEnabled(course is not None and not course_removed)
        self.rename_lecture_btn.setEnabled(lecture is not None and not course_removed)
        self.remove_lecture_btn.setEnabled(lecture is not None and not course_removed and not lecture_removed and not protected_lecture)
        self.remove_lecture_btn.setVisible(not lecture_removed)
        self.restore_lecture_btn.setVisible(lecture_removed)
        self.restore_lecture_btn.setEnabled(lecture_removed and not course_removed)
        self.notice.setText("Stop and save the active session before removing its course or lecture. Renaming keeps its history."
                            if protected_course else "Removed items can be restored using Show removed items.")

    def _commit(self, action, created=None):
        cid, lid = self.course.currentData(), self._lecture_id()
        try:
            result = action()
        except (ValueError, KeyError, OSError) as error:
            QMessageBox.warning(self, "Could not save change", str(error))
            return False
        self.reload(result if created == "course" else cid,
                    result if created == "lecture" else lid)
        return True

    def _add_course(self):
        name, ok = QInputDialog.getText(self, "Add course", "Course name:")
        if ok:
            self._commit(lambda: stats.create_course(name), "course")

    def _rename_course(self):
        cid = self.course.currentData()
        if cid is None:
            return
        name, ok = QInputDialog.getText(self, "Rename course", "Course name:", text=self._courses[cid]["name"])
        if ok:
            self._commit(lambda: stats.rename_course(cid, name))

    def _remove_course(self):
        cid = self.course.currentData()
        if cid is None or cid == self.protected_context[0]:
            return
        if QMessageBox.question(self, "Remove course", "Remove this course and its lectures from the timer?\nStudy history stays in Trends. You can restore the course later.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._commit(lambda: stats.delete_course(cid))

    def _restore_course(self):
        cid = self.course.currentData()
        if cid is not None:
            self._commit(lambda: stats.restore_course(cid))

    def _add_lecture(self):
        cid = self.course.currentData()
        if cid is None:
            return
        name, ok = QInputDialog.getText(self, "Add lecture", "Lecture name:")
        if ok:
            self._commit(lambda: stats.create_lecture(cid, name), "lecture")

    def _rename_lecture(self, *_):
        cid, lid = self.course.currentData(), self._lecture_id()
        if lid is None:
            return
        name, ok = QInputDialog.getText(self, "Rename lecture", "Lecture name:", text=self._courses[cid]["lectures"][lid]["name"])
        if ok:
            self._commit(lambda: stats.rename_lecture(cid, lid, name))

    def _remove_lecture(self):
        cid, lid = self.course.currentData(), self._lecture_id()
        if lid is None or (cid, lid) == self.protected_context:
            return
        if QMessageBox.question(self, "Remove lecture", "Remove this lecture from the timer?\nIts study history stays in Trends. You can restore it later.",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._commit(lambda: stats.delete_lecture(cid, lid))

    def _restore_lecture(self):
        cid, lid = self.course.currentData(), self._lecture_id()
        if lid is not None:
            self._commit(lambda: stats.restore_lecture(cid, lid))
